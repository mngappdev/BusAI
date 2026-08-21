import json
import logging
import math
import requests
import os
from datetime import datetime, timezone
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()  # picks up LTA_API_KEY (and anything else) from a .env file, if present

LTA_API_BASE = "https://datamall2.mytransport.sg/ltaodataservice"
logger = logging.getLogger(__name__)

class BusSmartEngine:
    def __init__(self):
        base_path = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base_path, "bus_routes.json"), 'r', encoding='utf-8') as f:
            self.routes = json.load(f)
        with open(os.path.join(base_path, "bus_stops.json"), 'r', encoding='utf-8') as f:
            self.stops = json.load(f)

        self.stop_map = {s['BusStopCode']: s for s in self.stops if 'BusStopCode' in s}
        self.stop_to_routes = defaultdict(list)
        for r in self.routes:
            self.stop_to_routes[r['BusStopCode']].append(r)
        self._arrival_cache = {}

        self.berth_map = self._load_berth_map(base_path)
        self.berth_lookup = self._build_berth_lookup()
        self.nearby_places_data = self._load_nearby_places(base_path)

        self._initialize_data()

    def _initialize_data(self):
        # Build service_to_route: {(ServiceNo, Direction): [{ BusStopCode, StopSequence, Distance, Latitude, Longitude }]}
        self.service_to_route = {}
        for r in self.routes:
            key = (r['ServiceNo'], r['Direction'])
            if key not in self.service_to_route:
                self.service_to_route[key] = []
            stop_info = self.stop_map.get(r['BusStopCode'], {})
            self.service_to_route[key].append({
                'BusStopCode': r['BusStopCode'],
                'StopSequence': int(r['StopSequence']),
                'Distance': float(r.get('Distance', 0)),
                'Latitude': float(stop_info.get('Latitude', 0)),
                'Longitude': float(stop_info.get('Longitude', 0)),
            })
        for key in self.service_to_route:
            self.service_to_route[key].sort(key=lambda x: x['StopSequence'])

    def _load_berth_map(self, base_path):
        try:
            with open(os.path.join(base_path, "berth_map.json"), 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def _load_nearby_places(self, base_path):
        try:
            with open(os.path.join(base_path, "nearby_places.json"), 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"categories": [], "places": []}

    def nearby_places(self, lat, lon):
        """Curated points of interest around Pasir Ris Bus Interchange, with
        distance and walk time computed live from the given location — the
        data file only stores each place's own fixed coordinates.
        """
        WALK_MIN_PER_KM = 12  # same pace used for the trip planner's walk legs

        places = []
        for place in self.nearby_places_data.get('places', []):
            distance_m = self.haversine(lat, lon, place['lat'], place['lon'])
            places.append({
                **place,
                'distance_m': int(round(distance_m)),
                'walk_minutes': int(round((distance_m / 1000) * WALK_MIN_PER_KM)),
            })
        places.sort(key=lambda p: (p['category'], p['distance_m']))

        return {
            'categories': self.nearby_places_data.get('categories', []),
            'places': places,
        }

    def _build_berth_lookup(self):
        """Map (stop, service) -> every berth that service boards from.

        A looping service uses a different berth per direction (359 boards at
        B4 westbound and B6 eastbound), so this is deliberately a list.
        """
        lookup = {}
        for stop_code, info in self.berth_map.items():
            for entry in info.get('boarding', []):
                for svc in entry.get('services', []):
                    lookup.setdefault((stop_code, svc), []).append(entry['berth'])
        return lookup

    def get_berth_options(self, stop_code, service_no):
        return list(self.berth_lookup.get((stop_code, str(service_no)), []))

    def get_berth(self, stop_code, service_no):
        """The berth, but only when there is exactly one.

        Our route data carries no loop-direction field, so for a service with
        two berths we cannot tell which one applies. Naming one would be wrong
        half the time; callers should fall back to get_berth_options.
        """
        berths = self.berth_lookup.get((stop_code, str(service_no)), [])
        return berths[0] if len(berths) == 1 else None

    # ─── Utilities ────────────────────────────────────────────────────────────

    def _route_key(self, route):
        return (route.get('ServiceNo'), route.get('Direction'))

    def haversine(self, lat1, lon1, lat2, lon2):
        R = 6371000
        p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
        dphi  = math.radians(float(lat2) - float(lat1))
        dlamb = math.radians(float(lon2) - float(lon1))
        a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlamb / 2) ** 2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _stop_payload(self, stop, user_lat=None, user_lon=None):
        payload = {
            'code': stop['BusStopCode'],
            'name': stop.get('Description', ''),
            'latitude': float(stop['Latitude']),
            'longitude': float(stop['Longitude']),
        }
        if user_lat is not None and user_lon is not None:
            payload['distance_m'] = int(round(self.haversine(user_lat, user_lon, stop['Latitude'], stop['Longitude'])))
        return payload

    def _candidate_stops(self, lat, lon, radius_m=400):
        return [
            s['BusStopCode']
            for s in self.stops
            if self.haversine(lat, lon, s['Latitude'], s['Longitude']) <= radius_m
        ]

    # ─── Real-time arrivals ───────────────────────────────────────────────────

    def _parse_arrival_payload(self, payload):
        services = payload.get('Services', []) if isinstance(payload, dict) else []
        arrival_map = {}
        for svc in services:
            service_no = svc.get('ServiceNo')
            next_bus = svc.get('NextBus', {}) or {}
            est_time = next_bus.get('EstimatedArrival')
            if not service_no or not est_time:
                continue
            try:
                eta_dt = datetime.fromisoformat(est_time.replace('Z', '+00:00'))
                diff = (eta_dt - datetime.now(timezone.utc)).total_seconds() / 60
            except Exception:
                continue
            load_map = {'SEA': '有座', 'SDA': '较挤', 'LSD': '拥挤'}
            arrival_map[str(service_no)] = {
                'minutes': max(0, int(diff)),
                'load': load_map.get(next_bus.get('Load'), '未知'),
                'is_wab': next_bus.get('Feature') == 'WAB',
                'raw_eta': est_time,
            }
        return arrival_map

    def get_realtime_arrivals(self, stop_code):
        api_key = os.getenv('LTA_API_KEY')
        if not api_key:
            return {}
        cached = self._arrival_cache.get(stop_code)
        if cached and (datetime.now(timezone.utc) - cached[0]).total_seconds() < 20:
            return cached[1]
        headers = {'AccountKey': api_key, 'Accept': 'application/json'}
        url = 'https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival'
        try:
            r = requests.get(url, headers=headers, params={'BusStopCode': stop_code}, timeout=5)
            r.raise_for_status()
            arrivals = self._parse_arrival_payload(r.json())
            self._arrival_cache[stop_code] = (datetime.now(timezone.utc), arrivals)
            return arrivals
        except Exception:
            return {}

    def get_realtime_v3(self, stop_code, service_no):
        return self.get_realtime_arrivals(stop_code).get(str(service_no))

    # ─── Nearby stops ─────────────────────────────────────────────────────────

    def nearby_stops(self, lat, lon, radius_m=600, limit=8):
        nearby = []
        for stop in self.stops:
            d = self.haversine(lat, lon, stop['Latitude'], stop['Longitude'])
            if d <= radius_m:
                nearby.append(self._stop_payload(stop, lat, lon))
        nearby.sort(key=lambda x: x['distance_m'])
        for stop in nearby[:limit]:
            services = sorted(
                {r['ServiceNo'] for r in self.stop_to_routes.get(stop['code'], [])},
                key=lambda x: (len(x), x)
            )
            stop['services'] = services
            arrivals_by_svc = self.get_realtime_arrivals(stop['code'])
            arrivals, seen = [], set()
            for svc in services:
                if svc in seen:
                    continue
                seen.add(svc)
                live = arrivals_by_svc.get(svc)
                arrivals.append({
                    'service': svc,
                    'minutes': live['minutes'] if live else None,
                    'load': live['load'] if live else None,
                    'is_wab': live['is_wab'] if live else False,
                })
            arrivals.sort(key=lambda x: (x['minutes'] is None, x['minutes'] if x['minutes'] is not None else 9999, x['service']))
            stop['nearest_arrival'] = arrivals[0] if arrivals else None
            stop['arrivals'] = arrivals[:3]
        return nearby[:limit]

    # ─── Route planning ───────────────────────────────────────────────────────

    def _format_leg(self, s_code, e_code, r_start, r_end):
        """Build one journey leg including the stop-by-stop polyline for map drawing."""
        svc = r_start['ServiceNo']
        direction = r_start['Direction']
        start_seq = int(r_start['StopSequence'])
        end_seq = int(r_end['StopSequence'])

        full_path = self.service_to_route.get((svc, direction), [])
        polyline = [
            [stop['Latitude'], stop['Longitude']]
            for stop in full_path
            if start_seq <= stop['StopSequence'] <= end_seq
            and stop['Latitude'] != 0 and stop['Longitude'] != 0
        ]

        live = self.get_realtime_arrivals(s_code).get(str(svc))
        return {
            'service': svc,
            'from_code': s_code,
            'from_name': self.stop_map[s_code]['Description'],
            'to_code': e_code,
            'to_name': self.stop_map[e_code]['Description'],
            'stops': end_seq - start_seq,
            'dist_km': round(float(r_end['Distance']) - float(r_start['Distance']), 2),
            'polyline': polyline,
            'live': live,
            'berth': self.get_berth(s_code, svc),
            'berth_options': self.get_berth_options(s_code, svc),
        }

    def _find_direct_routes(self, start_cluster, end_cluster):
        raw = []
        for s_code in start_cluster:
            s_routes = {self._route_key(r): r for r in self.stop_to_routes.get(s_code, [])}
            for e_code in end_cluster:
                if s_code == e_code:
                    continue
                for r_end in self.stop_to_routes.get(e_code, []):
                    key = self._route_key(r_end)
                    if key in s_routes:
                        r_start = s_routes[key]
                        if int(r_end['StopSequence']) > int(r_start['StopSequence']):
                            raw.append(self._format_leg(s_code, e_code, r_start, r_end))
        return raw

    def _find_transfer_routes(self, start_cluster, end_cluster):
        results = []
        # Index which routes can reach the end cluster
        target_routes = {}
        for e_code in end_cluster:
            for r in self.stop_to_routes.get(e_code, []):
                target_routes[self._route_key(r)] = (e_code, r)

        for s_code in start_cluster:
            for r_start_a in self.stop_to_routes.get(s_code, []):
                key_a = self._route_key(r_start_a)
                full_route_a = self.service_to_route.get(key_a, [])

                for hub in full_route_a:
                    if int(hub['StopSequence']) <= int(r_start_a['StopSequence']):
                        continue
                    hub_code = hub['BusStopCode']

                    for r_start_b in self.stop_to_routes.get(hub_code, []):
                        key_b = self._route_key(r_start_b)
                        if key_b == key_a:
                            continue
                        if key_b not in target_routes:
                            continue
                        e_code, r_end_b = target_routes[key_b]
                        if int(r_end_b['StopSequence']) <= int(r_start_b['StopSequence']):
                            continue

                        leg1 = self._format_leg(s_code, hub_code, r_start_a, hub)
                        leg2 = self._format_leg(hub_code, e_code, r_start_b, r_end_b)
                        results.append({
                            'leg1': leg1,
                            'leg2': leg2,
                            'total_stops': leg1['stops'] + leg2['stops'],
                        })
                        if len(results) >= 5:
                            results.sort(key=lambda x: x['total_stops'])
                            return results

        results.sort(key=lambda x: x['total_stops'])
        return results

    def _process_options(self, raw_options):
        if not raw_options:
            return []
        # Dedup: keep fewest stops per service
        unique = {}
        for opt in raw_options:
            svc = opt['service']
            if svc not in unique or opt['stops'] < unique[svc]['stops']:
                unique[svc] = opt

        final = list(unique.values())
        for opt in final:
            if opt.get('live') is None:
                opt['live'] = self.get_realtime_v3(opt['from_code'], opt['service'])
            wait = opt['live']['minutes'] if opt.get('live') and opt['live']['minutes'] is not None else 18
            opt['confidence'] = max(0, 100 - opt['stops'] * 8 - wait)

        final.sort(key=lambda x: (
            0 if x.get('live') and x['live']['minutes'] is not None else 1,
            x['live']['minutes'] if x.get('live') and x['live']['minutes'] is not None else 999,
            x['stops'],
        ))
        return final

    def best_route_candidates(self, s_lat, s_lon, e_lat, e_lon):
        dist = self.haversine(s_lat, s_lon, e_lat, e_lon)
        if dist < 800:
            return {
                'type': 'walk',
                'dist_m': round(dist),
                'minutes': max(1, round(dist / 80)),
                'message': '目的地很近，建议步行。',
            }

        start_cluster = self._candidate_stops(s_lat, s_lon, 400)
        end_cluster   = self._candidate_stops(e_lat, e_lon, 400)
        if not start_cluster or not end_cluster:
            return {'type': 'none', 'message': '起点或终点周边暂无可用巴士站。'}

        direct = self._find_direct_routes(start_cluster, end_cluster)
        if direct:
            processed = self._process_options(direct)
            return {
                'type': 'bus',
                'mode': 'direct',
                'best': processed[0] if processed else None,
                'options': processed[:3],
                'message': '为您找到直达巴士方案。',
            }

        transfer = self._find_transfer_routes(start_cluster, end_cluster)
        if transfer:
            return {
                'type': 'bus',
                'mode': 'transfer',
                'options': transfer[:2],
                'message': '直达不可行，已为您计算转乘方案。',
            }

        return {'type': 'none', 'message': '暂无直达或一次转乘的巴士方案。'}

    def plan_trip(self, s_lat, s_lon, e_lat, e_lon):
        return self.best_route_candidates(s_lat, s_lon, e_lat, e_lon)

    # ─── Route summary ────────────────────────────────────────────────────────

    def route_summary(self, service_no):
        entries = [r for r in self.routes if r['ServiceNo'] == service_no]
        if not entries:
            return None
        entries.sort(key=lambda x: (int(x.get('Direction', 0)), int(x.get('StopSequence', 0))))
        grouped = {}
        for r in entries:
            key = str(r.get('Direction', '1'))
            grouped.setdefault(key, []).append({
                'stop_code': r['BusStopCode'],
                'stop_name': self.stop_map.get(r['BusStopCode'], {}).get('Description', ''),
                'sequence': int(r.get('StopSequence', 0)),
                'distance_km': float(r.get('Distance', 0)),
            })
        return {'service': service_no, 'directions': grouped}

    # ─── External API helpers ─────────────────────────────────────────────────

    def _fetch_lta_feed(self, feed_name, path):
        """Shared fetch for the LTA DataMall "Alerts" feeds. An empty ticker
        and a missing/rejected credential looked identical before this: both
        silently returned []. Logging here is what makes the difference
        diagnosable instead of reading as "genuinely zero incidents."
        """
        api_key = os.getenv('LTA_API_KEY')
        if not api_key:
            logger.warning(
                "%s: LTA_API_KEY is not set — returning no alerts instead of "
                "calling LTA DataMall. Set LTA_API_KEY to enable this feed.",
                feed_name,
            )
            return []
        headers = {'AccountKey': api_key, 'Accept': 'application/json'}
        try:
            r = requests.get(f'{LTA_API_BASE}/{path}', headers=headers, timeout=5)
            r.raise_for_status()
            return r.json().get('value', [])
        except Exception as exc:
            logger.warning("%s: request to LTA DataMall failed: %s", feed_name, exc)
            return []

    def get_traffic_incidents(self):
        return self._fetch_lta_feed('TrafficIncidents', 'TrafficIncidents')

    def get_train_service_alerts(self):
        return self._fetch_lta_feed('TrainServiceAlerts', 'TrainServiceAlerts')

    def get_facilities_maintenance(self):
        return self._fetch_lta_feed('FacilitiesMaintenance', 'v2/FacilitiesMaintenance')

    def get_air_temperature(self, lat=None, lon=None):
        api_key = 'v2:c301d3e632007d24480125f32e20315e53467c6bca4707f4cc08a8dbe9353a74:uR417bu2gr6LnnYc14EzFWgRT9iHKsgb'
        headers = {'api-key': api_key}
        try:
            r = requests.get(
                'https://api-open.data.gov.sg/v2/real-time/api/air-temperature',
                headers=headers, timeout=5
            )
            r.raise_for_status()
            readings = r.json()['data']['readings'][0]['data']
            for rec in readings:
                if rec.get('stationId') == 'S24':
                    return rec.get('value')
            if lat is not None and lon is not None:
                nearest = min(readings, key=lambda rec: self.haversine(
                    lat, lon, rec.get('latitude', 0), rec.get('longitude', 0)
                ))
                return nearest.get('value')
            vals = [rec.get('value') for rec in readings if 'value' in rec]
            return sum(vals) / len(vals) if vals else None
        except Exception:
            return None

    def get_two_hr_forecast(self, lat=None, lon=None):
        api_key = 'v2:c301d3e632007d24480125f32e20315e53467c6bca4707f4cc08a8dbe9353a74:uR417bu2gr6LnnYc14EzFWgRT9iHKsgb'
        headers = {'api-key': api_key}
        try:
            r = requests.get(
                'https://api-open.data.gov.sg/v2/real-time/api/two-hr-forecast',
                headers=headers, timeout=5
            )
            r.raise_for_status()
            data = r.json()
            area_metadata = data['data']['area_metadata']
            forecasts = data['data']['items'][0]['forecasts']
            forecast_lookup = {f['area']: f['forecast'] for f in forecasts}
            if lat is not None and lon is not None:
                closest = min(
                    area_metadata,
                    key=lambda a: self.haversine(
                        lat, lon,
                        a['label_location']['latitude'],
                        a['label_location']['longitude']
                    )
                )
                area_name = closest['name']
            else:
                area_name = 'Changi'
            return [{'area': area_name, 'forecast': forecast_lookup.get(area_name, 'N/A')}]
        except Exception:
            return [{'area': 'N/A', 'forecast': 'N/A'}]
