from flask_mongoengine.wtf import model_form
from flask_admin.contrib.mongoengine import ModelView
from app import db, admin

class Config(db.EmbeddedDocument):
    name = db.StringField()
    param2 = db.StringField(max_length=3)


#ConfigForm = model_form(Config)

# Customized admin views
class ConfigView(ModelView):
    column_filters = ['name']

    # form_ajax_refs = {
    #     'tags': {
    #         'fields': ('name',)
    #     }
    # }


admin.add_view(ConfigView(Config))