from wtforms import Form, StringField, validators
from flask_wtf import FlaskForm

# form class with static fields
class StepForm(FlaskForm):
  name = StringField('Name', [validators.Length(min=6, max=35)])

  def __init__(self, record):
    for key, value in record.items():
      setattr(self, key, StringField(value))