from flask_mongoengine.wtf import model_form
from mongoengine import (EmbeddedDocument, EmbeddedDocumentField,
                         connect, DecimalField, StringField, IntField, ListField, Document)

from flask_admin.contrib.mongoengine import ModelView
from app import db, admin

class Config(Document):
    name = StringField()
    number1 = IntField()
    number2 = IntField()
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