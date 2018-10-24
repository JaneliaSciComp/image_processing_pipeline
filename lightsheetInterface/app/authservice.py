import base64
import json, requests
from datetime import datetime

from flask_login import login_user, UserMixin, logout_user

from app import login_manager, app


def create_auth_service():
    return AuthenticationService(app.config.get('AUTH_SERVICE_URL'))


@login_manager.user_loader
def token_validator(user_token):
    auth_service = create_auth_service()
    return auth_service.validate_user_token(user_token)


class User(UserMixin):
    def __init__(self, token=None, username=None):
        token_components = token.split('.')
        user_token_comp = token_components[1]
        user_token_comp += "=" * ((4 - len(user_token_comp) % 4) % 4)
        user_fields = json.loads(base64.b64decode(user_token_comp).decode('UTF-8'))
        self._token = token
        self.username = username if username is not None else user_fields.get('user_name')
        self._user_fields = user_fields

    def get_id(self):
        return self._token

    @property
    def is_authenticated(self):
        exp = datetime.fromtimestamp(self._user_fields['exp'])
        return exp > datetime.now()

    def get_expiration(self):
        if self._user_fields:
            return datetime.fromtimestamp(self._user_fields['exp'])
        else:
            return datetime.now()


class AuthenticationService(object):
    def __init__(self, auth_url):
        self._auth_url = auth_url

    def authenticate(self, user_credentials):
        username = user_credentials.get('username')
        password = user_credentials.get('password')
        # validate the credentials
        headers = {'Content-type': 'application/json', 'Accept': 'application/json'}
        authResponse = requests.post(self._auth_url,
                                     headers=headers,
                                     data=json.dumps({'username': username, 'password': password}))
        if authResponse.status_code != 200:
            return False
        else:
            auth = authResponse.json()
            u = self._create_user(token=auth['token'], username=auth['user_name'])
            expiration_time = u.get_expiration() - datetime.now()
            login_user(u, duration=expiration_time)
            return True

    def validate_user_token(self, token):
        try:
            return self._create_user(token=token)
        except:
            return None

    def logout(self):
        logout_user()

    def _create_user(self, token=None, username=None):
        return User(token=token, username=username)
