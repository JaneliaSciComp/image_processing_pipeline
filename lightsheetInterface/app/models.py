from flask_mongoengine.wtf import model_form
from wtforms.widgets import TextArea
from mongoengine import (EmbeddedDocument, EmbeddedDocumentField,
                         connect, DecimalField, StringField, IntField, FloatField, ListField, BooleanField, Document, ReferenceField, NULLIFY)

from flask_admin.contrib.mongoengine import ModelView
from app import admin

types = (('', None), ('S','Step'), ('D','Directory'))
frequency = (('F', 'Frequent'), ('S','Sometimes'), ('R','Rare'))
formats = (('', None), ('R', 'Range'), ('A', 'Array'), ('C', 'Checkboxes'))

class AppConfig(Document):
    name = StringField(max_length=200)
    value = StringField(max_length=200)
    def __repr__(self):
      return self.name

class Parameter(Document):
    name = StringField(max_length=200)
    number1 = FloatField()
    number2 = FloatField()
    number3 = FloatField()
    number4 = FloatField()
    text1 = StringField(max_length=500)
    description = StringField(max_length=500)
    frequency = StringField(max_length=20, choices=frequency)
    formatting = StringField(max_length=20, choices=formats)
    order = IntField()
    def __unicode__(self):
      return self.name

class Step(Document):
    name = StringField(max_length=200)
    description = StringField(max_length=500)
    order = IntField()
    parameter = ListField(ReferenceField(Parameter))
    submit = BooleanField(default=True)
    def __unicode__(self):
      return self.name

class Dependency(Document):
    inputField = ReferenceField(Parameter)
    outputField = ReferenceField(Parameter)
    pattern = StringField(max_length=200)

# Customized admin views
class ConfigView(ModelView):
    column_filters = ['name']

class StepView(ModelView):
    column_filters = ['name', 'description']

class ParameterView(ModelView):
    column_filters = ['name', 'description', 'frequency', 'formatting']

class DependecyView(ModelView):
    column_filters = ['inputField', 'outputField', 'pattern']
    column_labels = dict(inputField='Input',
                        outputField='Output',
                        pattern='Pattern')

admin.add_view(ConfigView(AppConfig))
admin.add_view(StepView(Step))
admin.add_view(ParameterView(Parameter))
admin.add_view(DependecyView(Dependency))