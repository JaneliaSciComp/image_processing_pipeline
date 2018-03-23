from wtforms import Form, StringField, validators
from flask_wtf import FlaskForm

# form class with static fields
class StepForm(Form):
  name = StringField('Name', [validators.Length(min=6, max=35)])