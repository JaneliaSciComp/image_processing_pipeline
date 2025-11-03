from flask_wtf import FlaskForm
from wtforms.validators import DataRequired
from wtforms import StringField, PasswordField


class LoginForm(FlaskForm):
    username = StringField('username',
                           validators=[DataRequired('Username is required')])
    password = PasswordField('password')
