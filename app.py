"""
Safety-Aware Route Planner — Flask application entry point.
"""
import os
import json
import logging
import logging.handlers
from datetime import datetime

from flask import (Flask, render_template, request, jsonify,
                   redirect, url_for, flash, abort)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash

from config import config
from models import db, User, Guardian, IncidentReport, ActiveTraveler
from safety_scoring import load_graph, calculate_edge_safety, get_edge_safety
from routing import find_safest_route, compute_route_geojson
from ml_model import predict_risk, load_model
from utils import compute_confidence, find_safety_twins, check_rate_limit, validate_latlng


# ── Application factory ───────────────────────────────────────────────────────

def create_app(env: str | None = None) -> Flask:
    env = env or os.environ.get('FLASK_ENV', 'development')
    app = Flask(__name__)
    app.config.from_object(config.get(env, config['default']))

    _configure_logging(app)
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view      = 'login'
    login_manager.login_message   = 'Please log in to access this page.'

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        return User.query.get(int(user_id))

    _register_error_handlers(app)
    return app


def _configure_logging(app: Flask) -> None:
    level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO').upper(), logging.INFO)
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    handlers = [logging.StreamHandler()]
    try:
        fh = logging.handlers.RotatingFileHandler(
            app.config['LOG_FILE'], maxBytes=5_000_000, backupCount=3
        )
        fh.setFormatter(formatter)
        handlers.append(fh)
    except Exception:
        pass

    for h in handlers:
        h.setFormatter(formatter)

    logging.basicConfig(level=level, handlers=handlers)
    app.logger.setLevel(level)


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(400)
    def bad_request(e):
        if request.is_json:
            return jsonify(error=str(e)), 400
        return render_template('errors/400.html'), 400

    @app.errorhandler(403)
    def forbidden(e):
        if request.is_json:
            return jsonify(error='Forbidden'), 403
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        if request.is_json:
            return jsonify(error='Not found'), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(429)
    def rate_limited(e):
        return jsonify(error='Too many requests'), 429

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Unhandled 500: %s", e)
        if request.is_json:
            return jsonify(error='Internal server error'), 500
        return render_template('errors/500.html'), 500


# ── Create app instance ───────────────────────────────────────────────────────

app = create_app()
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Auth routes
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email',    '').strip().lower()
        password = request.form.get('password', '')

        # --- Validation ---
        errors = []
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if not email or '@' not in email:
            errors.append('A valid email is required.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if User.query.filter_by(username=username).first():
            errors.append('Username already taken.')
        if User.query.filter_by(email=email).first():
            errors.append('Email already registered.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('register.html')

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        login_user(user, remember=False)
        logger.info("New user registered: %s", username)
        flash('Welcome! Your account has been created.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=remember)
            user.last_login = datetime.utcnow()
            db.session.commit()
            logger.info("User logged in: %s", user.username)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))

        flash('Invalid email or password.', 'danger')
        logger.warning("Failed login attempt for email: %s", email)

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logger.info("User logged out: %s", current_user.username)
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# ═══════════════════════════════════════════════════════════════════════════════
# Page routes
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/dashboard')
@login_required
def dashboard():
    recent_reports = (
        IncidentReport.query
        .filter_by(reporter_id=current_user.id)
        .order_by(IncidentReport.timestamp.desc())
        .limit(5)
        .all()
    )
    return render_template('dashboard.html', recent_reports=recent_reports)


@app.route('/plan_route', methods=['GET', 'POST'])
@login_required
def plan_route():
    if request.method == 'POST':
        try:
            orig_lat = float(request.form['origin_lat'])
            orig_lng = float(request.form['origin_lng'])
            dest_lat = float(request.form['dest_lat'])
            dest_lng = float(request.form['dest_lng'])
        except (KeyError, ValueError):
            flash('Invalid coordinates. Please click on the map to set origin and destination.', 'danger')
            return redirect(url_for('plan_route'))

        if not (validate_latlng(orig_lat, orig_lng) and validate_latlng(dest_lat, dest_lng)):
            flash('Coordinates out of valid range.', 'danger')
            return redirect(url_for('plan_route'))

        try:
            G     = load_graph()
            route = find_safest_route(G, (orig_lat, orig_lng), (dest_lat, dest_lng))
        except Exception as exc:
            logger.exception("Route computation error: %s", exc)
            flash('Route computation failed. Please try again.', 'danger')
            return redirect(url_for('plan_route'))

        if not route:
            flash('No route found between those points.', 'warning')
            return redirect(url_for('plan_route'))

        geojson = compute_route_geojson(G, route['path_nodes'])
        twins   = find_safety_twins(current_user.id, route['path_nodes'], datetime.utcnow())

        return render_template(
            'plan_route.html',
            route=route,
            geojson=json.dumps(geojson),
            twins=twins,
            origin=[orig_lat, orig_lng],
            destination=[dest_lat, dest_lng],
            map_center=app.config['MAP_CENTER'],
            map_zoom=app.config['MAP_ZOOM'],
        )

    return render_template('plan_route.html',
                           map_center=app.config['MAP_CENTER'],
                           map_zoom=app.config['MAP_ZOOM'])


@app.route('/heatmap')
def heatmap():
    return render_template('heatmap.html',
                           map_center=app.config['MAP_CENTER'],
                           map_zoom=app.config['MAP_ZOOM'])


@app.route('/report')
@login_required
def report_page():
    return render_template('report.html',
                           map_center=app.config['MAP_CENTER'],
                           map_zoom=app.config['MAP_ZOOM'])


@app.route('/guardians', methods=['GET', 'POST'])
@login_required
def guardians():
    if request.method == 'POST':
        name  = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        if not email or '@' not in email:
            flash('A valid email is required.', 'danger')
        else:
            existing = Guardian.query.filter_by(
                user_id=current_user.id, guardian_email=email
            ).first()
            if existing:
                flash('That guardian is already added.', 'warning')
            else:
                db.session.add(Guardian(user_id=current_user.id, name=name, guardian_email=email))
                db.session.commit()
                flash(f'Guardian {name or email} added.', 'success')
        return redirect(url_for('guardians'))

    my_guardians = Guardian.query.filter_by(user_id=current_user.id).all()
    return render_template('guardians.html', guardians=my_guardians)


@app.route('/guardians/<int:g_id>/delete', methods=['POST'])
@login_required
def delete_guardian(g_id: int):
    g = Guardian.query.get_or_404(g_id)
    if g.user_id != current_user.id:
        abort(403)
    db.session.delete(g)
    db.session.commit()
    flash('Guardian removed.', 'info')
    return redirect(url_for('guardians'))


# ═══════════════════════════════════════════════════════════════════════════════
# API routes
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/route', methods=['POST'])
@login_required
def api_route():
    data = request.get_json(silent=True)
    if not data:
        return jsonify(success=False, message='Invalid JSON'), 400

    try:
        orig_lat, orig_lng = float(data['origin'][0]),      float(data['origin'][1])
        dest_lat, dest_lng = float(data['destination'][0]), float(data['destination'][1])
    except (KeyError, TypeError, ValueError):
        return jsonify(success=False, message='origin and destination must be [lat, lng]'), 400

    if not (validate_latlng(orig_lat, orig_lng) and validate_latlng(dest_lat, dest_lng)):
        return jsonify(success=False, message='Coordinates out of range'), 400

    try:
        G     = load_graph()
        route = find_safest_route(G, (orig_lat, orig_lng), (dest_lat, dest_lng))
    except Exception as exc:
        logger.exception("api_route error: %s", exc)
        return jsonify(success=False, message='Internal routing error'), 500

    if not route:
        return jsonify(success=False, message='No route found')

    geojson = compute_route_geojson(G, route['path_nodes'])
    twins   = find_safety_twins(current_user.id, route['path_nodes'], datetime.utcnow())

    return jsonify(success=True, route=route, geojson=geojson, twins=twins)


@app.route('/api/report', methods=['POST'])
@login_required
def submit_report():
    # Rate limiting: 10 reports per hour per user
    if not check_rate_limit(f'report:{current_user.id}', max_calls=10, window_seconds=3600):
        return jsonify(success=False, message='Too many reports. Try again later.'), 429

    data = request.get_json(silent=True)
    if not data:
        return jsonify(success=False, message='Invalid JSON'), 400

    try:
        lat      = float(data['lat'])
        lng      = float(data['lng'])
        rtype    = str(data.get('type', 'other'))
        severity = int(data.get('severity', 1))
        desc     = str(data.get('description', ''))[:1000]
    except (KeyError, ValueError, TypeError):
        return jsonify(success=False, message='Missing or invalid fields'), 400

    if not validate_latlng(lat, lng):
        return jsonify(success=False, message='Invalid coordinates'), 400

    if rtype not in IncidentReport.VALID_TYPES:
        rtype = 'other'

    severity = max(1, min(5, severity))

    report = IncidentReport(
        reporter_id=current_user.id,
        latitude=lat,
        longitude=lng,
        report_type=rtype,
        description=desc,
        severity=severity,
    )
    db.session.add(report)
    db.session.commit()
    logger.info("Incident report #%d submitted by user %d", report.id, current_user.id)
    return jsonify(success=True, report_id=report.id)


@app.route('/api/heatmap_data')
def heatmap_data():
    reports = (
        IncidentReport.query
        .filter_by(resolved=False)
        .order_by(IncidentReport.timestamp.desc())
        .limit(500)
        .all()
    )
    points = [[r.latitude, r.longitude, r.severity * 0.2] for r in reports]
    return jsonify(points)


@app.route('/api/update_location', methods=['POST'])
@login_required
def update_location():
    data = request.get_json(silent=True)
    if not data:
        return jsonify(success=False, message='Invalid JSON'), 400

    try:
        lat         = float(data['lat'])
        lng         = float(data['lng'])
        route_nodes = data.get('route_nodes', [])
    except (KeyError, ValueError, TypeError):
        return jsonify(success=False, message='lat and lng required'), 400

    if not validate_latlng(lat, lng):
        return jsonify(success=False, message='Invalid coordinates'), 400

    active = ActiveTraveler.query.filter_by(user_id=current_user.id).first()
    if active:
        active.latitude    = lat
        active.longitude   = lng
        active.route_nodes = route_nodes
        active.last_update = datetime.utcnow()
    else:
        active = ActiveTraveler(
            user_id=current_user.id,
            latitude=lat,
            longitude=lng,
            start_time=datetime.utcnow(),
            last_update=datetime.utcnow(),
        )
        active.route_nodes = route_nodes
        db.session.add(active)

    db.session.commit()
    return jsonify(success=True)


@app.route('/api/sos', methods=['POST'])
@login_required
def sos():
    guardians = Guardian.query.filter_by(user_id=current_user.id).all()
    if not guardians:
        return jsonify(success=False, message='No guardians configured. Add one under Guardians.'), 400

    active = ActiveTraveler.query.filter_by(user_id=current_user.id).first()
    location_str = (
        f"lat={active.latitude:.5f}, lng={active.longitude:.5f}"
        if active else "unknown"
    )
    alert_msg = (
        f"🚨 SOS from {current_user.username}!\n"
        f"They may need help at: {location_str}\n"
        f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    )

    sent = 0
    for g in guardians:
        # Replace with real email sending (Flask-Mail / SendGrid / etc.)
        logger.warning("SOS email → %s: %s", g.guardian_email, alert_msg)
        sent += 1

    return jsonify(success=True, message=f'SOS sent to {sent} guardian(s).', sent=sent)


@app.route('/api/predict_risk', methods=['POST'])
@login_required
def predict_risk_api():
    data = request.get_json(silent=True) or {}
    now  = datetime.utcnow()
    try:
        hour         = int(data.get('hour',          now.hour))
        day          = int(data.get('day',           now.weekday()))
        road_type    = int(data.get('road_type',     0))
        lighting     = int(data.get('lighting',      1))
        police_dist  = float(data.get('police_dist', 500))
        crowd        = float(data.get('crowd_density', 30))
        reports      = int(data.get('recent_reports',  0))
    except (ValueError, TypeError):
        return jsonify(error='Invalid parameters'), 400

    risk = predict_risk(hour, day, road_type, lighting, police_dist, crowd, reports)
    return jsonify(risk=round(risk, 1))


@app.route('/api/reports')
@login_required
def list_reports():
    """Paginated list of reports — admin/debugging use."""
    page  = max(1, request.args.get('page', 1, type=int))
    per   = min(50, request.args.get('per_page', 20, type=int))
    q     = IncidentReport.query.order_by(IncidentReport.timestamp.desc())
    pag   = q.paginate(page=page, per_page=per, error_out=False)
    return jsonify(
        items=[r.to_dict() for r in pag.items],
        total=pag.total,
        page=pag.page,
        pages=pag.pages,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Startup
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        logger.info("Database tables ensured.")
        try:
            G = load_graph()
            calculate_edge_safety(G)
        except Exception as exc:
            logger.warning("Could not initialise graph/safety scores: %s", exc)
        # Pre-warm the ML model
        try:
            load_model()
        except Exception as exc:
            logger.warning("ML model pre-warm failed: %s", exc)

    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    app.run(debug=debug, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
