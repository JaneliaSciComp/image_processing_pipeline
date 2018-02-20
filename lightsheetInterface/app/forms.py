from wtforms import Form, TextField, TextAreaField

class ContactForm(Form):
    name = TextField('Name')
    email = TextField('Email Address')
    body = TextAreaField('Message Body')