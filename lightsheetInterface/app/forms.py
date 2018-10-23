from flask_wtf import Form
from wtforms.validators import DataRequired
from wtforms import StringField, PasswordField


class LoginForm(Form):
    username = StringField('username',
                           validators=[DataRequired('Username is required')])
    password = PasswordField('password')
