import os
import requests
import json
from flask import Flask
from flask import request
from os.path import exists
from datetime import datetime
from copy import deepcopy

app = Flask(__name__)


@app.route("/api/get_weather")
def get_weather_view():
    weather_token = os.environ.get("WEATHER_API_TOKEN")
    uv_token = os.environ.get("UV_TOKEN")
    city = request.args.get('city')
    if not city:
        return {'error': 'Have not city in request'}
    cities = ['Baku', 'Antalya']
    if city not in cities:
        return {'error': f'Citi {city} not allowed. Possible variants: {", ".join(cities)}'}
    return Engine(
        weather_token=weather_token,
        uv_token=uv_token,
    ).get(city)


class Engine:
    data_path = 'data.data'
    max_cache_seconds = 10 * 60

    def __init__(self, weather_token, uv_token):
        self.weather_token = weather_token
        self.uv_token = uv_token

    def fetch_weather(self, key):
        payload = {
            'q': key,
            'units': 'metric',
            'appid': self.weather_token,
        }
        r = requests.get(
            'https://api.openweathermap.org/data/2.5/weather',
            params=payload
        )
        return r.json()

    def fetch_uv(self, lat, lng):
        payload = {
            'lat': lat,
            'lng': lng,
        }
        headers = {'x-access-token': self.uv_token}
        r = requests.get(
            'https://api.openuv.io/api/v1/uv',
            params=payload,
            headers=headers
        )
        return r.json()

    def get_local_data(self, key):
        if not exists(self.data_path):
            return None
        with open(self.data_path, 'r') as t_in:
            data = json.loads(t_in.read())
        return data.get(key)

    def should_update(self, data):
        if not data:
            return True
        before_dt = datetime.fromisoformat(data['last_get'])
        delta = datetime.now() - before_dt
        return delta.seconds > self.max_cache_seconds

    def format_output(self, weather_data, uv_data, last_get):
        main = deepcopy(weather_data['main'])
        main['date_time'] = last_get
        main['uv_index'] = uv_data['result']['uv']
        main['uv_index_max'] = uv_data['result']['uv_max']
        return {
            'weather': weather_data['weather'][0],
            'main': main,
            'wind': weather_data['wind'],
        }

    def get_remote_data(self, key):
        weather_data = self.fetch_weather(key)
        coords = weather_data['coord']
        uv_data = self.fetch_uv(coords['lat'], coords['lon'])
        last_get = datetime.now().isoformat()
        return {
            'last_get': last_get,
            'weather_data': weather_data,
            'uv_data': uv_data,
            'output': self.format_output(weather_data, uv_data, last_get)
        }

    def save_data(self, data, key):
        old_data = {}
        if exists(self.data_path):
            with open(self.data_path, 'r') as t_in:
                old_data = json.loads(t_in.read())
        old_data[key] = data
        with open(self.data_path, 'w') as t_out:
            t_out.write(json.dumps(old_data, indent=4))

    def get(self, key='Baku'):
        data = self.get_local_data(key)
        if not self.should_update(data):
            return data['output']
        remote = self.get_remote_data(key)
        self.save_data(remote, key)
        return remote['output']


if __name__ == '__main__':
    print('================Init tokens==================')
    weather_token = os.environ.get("WEATHER_API_TOKEN")
    uv_token = os.environ.get("UV_TOKEN")
    print('weather_token', weather_token)
    print('uv_token', uv_token)
    print('==============End Init tokens================')
    app.run(host='0.0.0.0', port=8000)
