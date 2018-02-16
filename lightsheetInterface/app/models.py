from flask_mongoengine.wtf import model_form
from mongoengine import (EmbeddedDocument, EmbeddedDocumentField,
                         connect, DecimalField, StringField, IntField, FloatField, ListField, Document, ReferenceField, NULLIFY)

from flask_admin.contrib.mongoengine import ModelView
from app import db, admin

types = (('', None), ('S','Step'), ('D','Directory'))
frequency = (('F', 'Frequent'), ('S','Sometimes'), ('R','Rare'))

class Config(Document):
    name = StringField(max_length=100)
    number1 = IntField()
    number2 = IntField()
    number3 = IntField()
    text1 = StringField(max_length=100)
    parent = ReferenceField("self", reverse_delete_rule = NULLIFY)
    type = StringField(max_length=20, choices=types)
    def __repr__(self):
      return self.name

class Parameter(Document):
    name = StringField(max_length=100)
    number1 = FloatField()
    number2 = FloatField()
    number3 = FloatField()
    text1 = StringField(max_length=100)
    frequency = StringField(max_length=20, choices=frequency)
    def __unicode__(self):
      return self.name

class Step(Document):
    name = StringField(max_length=50)
    description = StringField(max_length=200)
    order = IntField()
    parameter = ListField(ReferenceField(Parameter))
    def __unicode__(self):
      return self.name

# Customized admin views
class ConfigView(ModelView):
    column_filters = ['name']

class StepView(ModelView):
    column_filters = ['name']

class ParameterView(ModelView):
    column_filters = ['name']

admin.add_view(ConfigView(Config))
admin.add_view(StepView(Step))
admin.add_view(ParameterView(Parameter))