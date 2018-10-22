from mongoengine import (EmbeddedDocument, EmbeddedDocumentField,
                         connect, DecimalField, StringField, IntField, FloatField, ListField, BooleanField, DateTimeField, Document, ReferenceField, NULLIFY)
from flask_admin.contrib.mongoengine import ModelView
from wtforms import TextAreaField
from wtforms.widgets import TextArea
from app import admin
import datetime, uuid

types = (('', None), ('S','Step'), ('D','Directory'))
frequency = (('F', 'Frequent'), ('S','Sometimes'), ('R','Rare'))
formats = (('', None), ('R', 'Range'), ('A', 'Array'), ('C', 'Checkboxes'), ('O', 'Option'), ('F', 'Flag'),('B','Radio Button'))
dependency_type = (('V', 'Value'), ('D', 'Dimension'))
templates = ( ('L', 'Lightsheet'), ('I', 'ImageProcessing'), ('C', 'Confocal') )
steptypes = (('', None), ('Si', 'Singularity'), ('Sp', 'Spark'), ('L', 'LightSheet') )

class AppConfig(Document):
  name = StringField(max_length=200)
  value = StringField(max_length=200)
  def __repr__(self):
    return self.name

class Parameter(Document):
  # fields, which store the descriptive data of a parameter
  name = StringField(max_length=200, unique=True, required=True)
  displayName = StringField(max_length=200)
  description = StringField(max_length=500)
  ignore = BooleanField()
  mount = BooleanField()
  frequency = StringField(max_length=20, choices=frequency)
  formatting = StringField(max_length=20, choices=formats)
  readonly = BooleanField()
  empty = BooleanField()
  order = IntField()
  hint = StringField()

  # fields, which store default value information
  number1 = FloatField()
  number2 = FloatField()
  number3 = FloatField()
  number4 = FloatField()
  text1 = StringField(max_length=500)
  text2 = StringField(max_length=500)
  text3 = StringField(max_length=500)
  text4 = StringField(max_length=500)

  boolean = BooleanField()
  
  def __unicode__(self):
    return self.name

class Step(Document):
  name = StringField(max_length=200, unique=True, required=True)
  description = StringField(max_length=500)
  parameter = ListField(ReferenceField(Parameter))
  submit = BooleanField(default=True)
  template = ListField(StringField(max_length=200, choices=templates))
  order = IntField(required=True)
  steptype = StringField(max_length=200, choices=steptypes)
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

# serves as a fact table --> has references to both steps and parameters but stores actual values needed to configure an
# existing pipeline
class ConfigurationInstance(Document):
  creation_date = DateTimeField()
  step = ReferenceField(Step)
  parameter = ReferenceField(Parameter)
  number1 = FloatField()
  number2 = FloatField()
  number3 = FloatField()
  number4 = FloatField()
  text1 = StringField(max_length=500)
  text2 = StringField(max_length=500)
  text3 = StringField(max_length=500)
  text4 = StringField(max_length=500)

  boolean = BooleanField()

  def __unicode__(self):
    return self.creation_date.strftime("%d/%m/%y-%H:%m")

  def save(self, *args, **kwargs):
    if not self.creation_date:
        self.creation_date = datetime.datetime.now()
    return super(ConfigurationInstance, self).save(*args, **kwargs)

class Configuration(Document):
  name = StringField(default=lambda: str(uuid.uuid4()), primary_key=True)
  instances = ListField(ReferenceField(ConfigurationInstance))

  def __unicode__(self):
    return self.name

class PipelineInstance(Document):
  name = StringField(default=lambda: str(uuid.uuid4()), primary_key=True)
  description = StringField()
  creation_date = DateTimeField()
  content = StringField()

  def save(self, *args, **kwargs):
    if not self.creation_date:
        self.creation_date = datetime.datetime.now()
    return super(PipelineInstance, self).save(*args, **kwargs)

  def __unicode__(self):
    return self.name

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

class ConfigurationView(ModelView):
  column_filters = ['name']

class ConfigurationInstanceView(ModelView):
  column_filters = ['creation_date']

class PipelineInstanceView(ModelView):
  column_filters = ['creation_date']

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
   form_columns = ["name", "displayName", "description", "number1", "number2", "number3", "number4", "text1", "text2", "text3", "text4", "boolean", "readonly", "ignore", "mount", "empty", "frequency", "formatting", "order", "hint"]
   column_filters = ["name", "displayName", "description", "number1", "number2", "number3", "number4",  "text1", "text2", "text3", "text4", "boolean", "mount", "frequency", "formatting", "ignore"]
   form_overrides = {
      'hint': CKTextAreaField
   }


admin.add_view(ConfigView(AppConfig))
admin.add_view(StepView(Step))
admin.add_view(TemplateView(Template))
admin.add_view(ExtendedParameterView(Parameter))
admin.add_view(DependecyView(Dependency))
admin.add_view(PipelineInstanceView(PipelineInstance))