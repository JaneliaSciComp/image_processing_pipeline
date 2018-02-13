from flask_mongoengine.wtf import model_form
from mongoengine import (EmbeddedDocument, EmbeddedDocumentField,
                         connect, DecimalField, StringField, IntField, ListField, Document)

from flask_admin.contrib.mongoengine import ModelView
from app import db, admin

types = (('', None), ('S','Step'), ('D','Directory'))

class Config(Document):
    name = StringField(max_length=100)
    number1 = IntField()
    number2 = IntField()
    number3 = IntField()
    type = StringField(max_length=20, choices=types)

    def __repr__(self):
      return self.name
    def get_queryset(self):
      notifications = Config.objects.all()


# Customized admin views
class ConfigView(ModelView):
    column_filters = ['name']

    # form_ajax_refs = {
    #     'tags': {
    #         'fields': ('name',)
    #     }
    # }


admin.add_view(ConfigView(Config))