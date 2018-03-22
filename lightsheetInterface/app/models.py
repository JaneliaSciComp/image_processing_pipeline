from flask_mongoengine.wtf import model_form
from wtforms.widgets import TextArea
from mongoengine import (EmbeddedDocument, EmbeddedDocumentField,
                         connect, DecimalField, StringField, IntField, FloatField, ListField, Document, ReferenceField, NULLIFY)

from flask_admin.contrib.mongoengine import ModelView
from app import admin

types = (('', None), ('S','Step'), ('D','Directory'))
frequency = (('F', 'Frequent'), ('S','Sometimes'), ('R','Rare'))
formats = (('', None), ('R', 'Range'))

class AppConfig(Document):
    name = StringField(max_length=100)
    value = StringField(max_length=200)
    def __repr__(self):
      return self.name

class Parameter(Document):
    name = StringField(max_length=100)
    number1 = FloatField()
    number2 = FloatField()
    number3 = FloatField()
    text1 = StringField(max_length=100)
    description = StringField(max_length=500)
    frequency = StringField(max_length=20, choices=frequency)
    formatting = StringField(max_length=20, choices=formats)
    def __unicode__(self):
      return self.name

class Step(Document):
    name = StringField(max_length=50)
    description = StringField(max_length=500)
    order = IntField()
    parameter = ListField(ReferenceField(Parameter))
    def __unicode__(self):
      return self.name

# Customized admin views
class ConfigView(ModelView):
    column_filters = ['name']

class StepView(ModelView):
    column_filters = ['name', 'description']

class ParameterView(ModelView):
    column_filters = ['name', 'description', 'frequency']

admin.add_view(ConfigView(AppConfig))
admin.add_view(StepView(Step))
admin.add_view(ParameterView(Parameter))