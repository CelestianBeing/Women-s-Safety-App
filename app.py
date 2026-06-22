from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
from datetime import datetime
from geopy.distance import geodesic

from config import Config
from models import db, User, Guardian, IncidentReport, ActiveTraveler
from safety_scoring import load_graph, calculate_edge_safety, get_edge_safety
from routing import find_safest_route, compute_route_geojson
from ml_model import predict_risk
from utils import compute_confidence, find_safety_twins

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------- Routes ----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed = generate_password_hash(password)
        user = User(username=username, email=email, password_hash=hashed)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/plan_route', methods=['GET', 'POST'])
@login_required
def plan_route():
    if request.method == 'POST':
        orig_lat = float(request.form['origin_lat'])
        orig_lng = float(request.form['origin_lng'])
        dest_lat = float(request.form['dest_lat'])
        dest_lng = float(request.form['dest_lng'])
        # Find safest route
        G = load_graph()
        route = find_safest_route(G, (orig_lat, orig_lng), (dest_lat, dest_lng))
        if not route:
            flash('No route found')
            return redirect(url_for('plan_route'))
        # GeoJSON for map
        geojson = compute_route_geojson(G, route['path_nodes'])
        # Confidence and safety twins
        twins = find_safety_twins(current_user.id, route['path_nodes'], datetime.utcnow())
        return render_template('plan_route.html',
                               route=route,
                               geojson=json.dumps(geojson),
                               twins=twins,
                               origin=[orig_lat, orig_lng],
                               destination=[dest_lat, dest_lng])
    return render_template('plan_route.html')

@app.route('/api/route', methods=['POST'])
@login_required
def api_route():
    data = request.get_json()
    orig_lat, orig_lng = data['origin']
    dest_lat, dest_lng = data['destination']
    G = load_graph()
    route = find_safest_route(G, (orig_lat, orig_lng), (dest_lat, dest_lng))
    if route:
        geojson = compute_route_geojson(G, route['path_nodes'])
        twins = find_safety_twins(current_user.id, route['path_nodes'], datetime.utcnow())
        return jsonify({
            'success': True,
            'route': route,
            'geojson': geojson,
            'twins': twins
        })
    return jsonify({'success': False, 'message': 'No route found'})

@app.route('/api/report', methods=['POST'])
@login_required
def submit_report():
    data = request.get_json()
    report = IncidentReport(
        reporter_id=current_user.id,
        latitude=data['lat'],
        longitude=data['lng'],
        report_type=data['type'],
        description=data.get('description', ''),
        severity=int(data.get('severity', 1))
    )
    db.session.add(report)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/heatmap_data')
def heatmap_data():
    reports = IncidentReport.query.all()
    points = []
    for r in reports:
        points.append([r.latitude, r.longitude, r.severity * 0.5])
    return jsonify(points)

@app.route('/api/update_location', methods=['POST'])
@login_required
def update_location():
    data = request.get_json()
    lat, lng = data['lat'], data['lng']
    route_nodes = data.get('route_nodes', [])
    # Update or create active traveler record
    active = ActiveTraveler.query.filter_by(user_id=current_user.id).first()
    if active:
        active.latitude = lat
        active.longitude = lng
        active.route_nodes_json = json.dumps(route_nodes)
        active.last_update = datetime.utcnow()
    else:
        active = ActiveTraveler(
            user_id=current_user.id,
            latitude=lat,
            longitude=lng,
            route_nodes_json=json.dumps(route_nodes),
            start_time=datetime.utcnow(),
            last_update=datetime.utcnow()
        )
        db.session.add(active)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/sos', methods=['POST'])
@login_required
def sos():
    # Send alert to guardians (mock)
    guardians = Guardian.query.filter_by(user_id=current_user.id).all()
    alert_msg = f"SOS! {current_user.username} needs help at last known location."
    for g in guardians:
        print(f"Email to {g.guardian_email}: {alert_msg}")
    return jsonify({'success': True, 'message': 'SOS alerts sent to guardians'})

@app.route('/api/predict_risk', methods=['POST'])
@login_required
def predict_risk_api():
    data = request.get_json()
    hour = datetime.utcnow().hour
    day = datetime.utcnow().weekday()
    road_type = int(data.get('road_type', 0))  # 0-3
    lighting = int(data.get('lighting', 2))    # estimate
    police_dist = float(data.get('police_dist', 500))
    crowd = float(data.get('crowd_density', 30))
    reports = int(data.get('recent_reports', 0))
    risk = predict_risk(hour, day, road_type, lighting, police_dist, crowd, reports)
    return jsonify({'risk': round(risk, 1)})

@app.route('/heatmap')
def heatmap():
    return render_template('heatmap.html')

@app.route('/report')
@login_required
def report_page():
    return render_template('report.html')

# ---------- Startup ----------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Initialize OSM graph and edge safety
        G = load_graph()
        calculate_edge_safety(G)
    app.run(debug=True, port=5000)