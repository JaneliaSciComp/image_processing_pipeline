from flask_mongoengine.wtf import model_form
from wtforms.widgets import TextArea
from mongoengine import (EmbeddedDocument, EmbeddedDocumentField,
                         connect, DecimalField, StringField, IntField, FloatField, ListField, BooleanField, Document, ReferenceField, NULLIFY, MultiLineStringField)
from flask_admin.contrib.mongoengine import ModelView
from wtforms import TextAreaField
from wtforms.widgets import TextArea
from app import admin

types = (('', None), ('S','Step'), ('D','Directory'))
frequency = (('F', 'Frequent'), ('S','Sometimes'), ('R','Rare'))
formats = (('', None), ('R', 'Range'), ('A', 'Array'), ('C', 'Checkboxes'), ('O', 'Option'), ('F', 'Flag'))
dependency_type = (('V', 'Value'), ('D', 'Dimension'))
templates = ( ('L', 'Lightsheet'), ('I', 'ImageProcessing'), ('C', 'Confocal') )

class AppConfig(Document):
    name = StringField(max_length=200)
    value = StringField(max_length=200)
    def __repr__(self):
      return self.name

class Parameter(Document):
    name = StringField(max_length=200, unique=True, required=True)
    displayName = StringField(max_length=200)
    description = StringField(max_length=500)
    number1 = FloatField()
    number2 = FloatField()
    number3 = FloatField()
    number4 = FloatField()
    text1 = StringField(max_length=500)
    boolean = BooleanField()
    frequency = StringField(max_length=20, choices=frequency)
    formatting = StringField(max_length=20, choices=formats)
    readonly = BooleanField()
    empty = BooleanField()
    order = IntField()
    hint = StringField()
    def __unicode__(self):
      return self.name

class Step(Document):
    name = StringField(max_length=200, unique=True, required=True)
    description = StringField(max_length=500)
    parameter = ListField(ReferenceField(Parameter))
    submit = BooleanField(default=True)
    template = ListField(StringField(max_length=200, choices=templates))
    order = IntField(required=True)

    def __unicode__(self):
      return self.name

class Template(Document):
    name = StringField(max_length=200, unique=True, required=True)
    steps = ListField(ReferenceField(Step))
    order = IntField(required=True)

    def __unicode__(self):
      return self.name

class Dependency(Document):
    inputField = ReferenceField(Parameter)
    outputField = ReferenceField(Parameter)
    outputStep = ReferenceField(Step)
    pattern = StringField(max_length=200)
    dependency_type = StringField(max_length=20, choices=dependency_type)

# Customized admin views
class ConfigView(ModelView):
    column_filters = ['name']

class StepView(ModelView):
    column_filters = ['name', 'description']

class ParameterView(ModelView):
    column_filters = ['name', 'description', 'frequency', 'formatting']

class TemplateView(ModelView):
    column_filters = ['name']

class DependecyView(ModelView):
    column_filters = ['inputField', 'outputField', 'pattern']
    column_labels = dict(inputField='Input',
                        outputField='Output',
                        outputStep='Step',
                        pattern='Pattern')

class CKTextAreaWidget(TextArea):
   def __call__(self, field, **kwargs):
      if kwargs.get('class'):
         kwargs['class'] += ' ckeditor'
      else:
         kwargs.setdefault('class', 'ckeditor')
      return super(CKTextAreaWidget, self).__call__(field, **kwargs)

class CKTextAreaField(TextAreaField):
   widget = CKTextAreaWidget()


class ExtendedParameterView(ModelView):
   extra_js = ['//cdn.ckeditor.com/4.6.0/standard/ckeditor.js']
   form_columns = ["name", "displayName", "description", "number1", "number2", "number3", "number4", "text1", "boolean", "frequency", "formatting", "empty", "order", "readonly", "hint"]
   column_filters = ["name", "displayName", "description", "number1", "number2", "number3", "number4",  "text1", "boolean", "frequency", "formatting"]
   form_overrides = {
      'hint': CKTextAreaField
   }


admin.add_view(ConfigView(AppConfig))
admin.add_view(StepView(Step))
admin.add_view(TemplateView(Template))
admin.add_view(ExtendedParameterView(Parameter))
admin.add_view(DependecyView(Dependency))