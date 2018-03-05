from wtforms import Form, StringField, validators

# form class with static fields
class StepForm(FlaskForm):

def __init__(self, record):
        self.record = record

def compose():
  # add dynamic fields
  for key, value in self.record.items():
    setattr(self, key, StringField(value))