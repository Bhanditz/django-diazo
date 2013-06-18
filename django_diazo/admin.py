import os
import zipfile
from logging import getLogger
from codemirror.widgets import CodeMirrorTextarea
from django import forms
from django.conf import settings
from django.contrib import admin
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from actions import enable_theme
from models import Theme
from utils import theme_path, theme_url


class IFrameWidget(forms.Widget):
    def render(self, name, value, attrs=None):
        content_url = ''
        unthemed_available = False
        if hasattr(settings, 'DIAZO_UNTHEMED_URLNAME') and settings.DIAZO_UNTHEMED_URLNAME:
            try:
                content_url = reverse(settings.DIAZO_UNTHEMED_URLNAME)
                unthemed_available = True
            except:
                pass

        if not unthemed_available:
            getLogger('django_diazo').warning('Please create a page that serves unthemed content '
                                              'and provide the DIAZO_UNTHEMED_URLNAME variable in your settings.')
        return mark_safe(render_to_string('django_diazo/iframe_widget.html', {
            'content_url': content_url,
            'theme_url': '/'.join([value, 'index.html']),  # value is filled with theme_url()
        }))


class ThemeForm(forms.ModelForm):
    upload = forms.FileField(required=False, label=_('Zip file'),
                             help_text=_('Will be unpacked in media directory.'))
    codemirror = CodeMirrorTextarea()
    rules_editor = forms.CharField(required=False, widget=codemirror)
    theme_mapper = forms.CharField(required=False, widget=IFrameWidget)

    class Meta:
        model = Theme

    def __init__(self, *args, **kwargs):
        if 'instance' in kwargs and kwargs['instance']:
            if not 'initial' in kwargs:
                kwargs['initial'] = {}
            rules = os.path.join(theme_path(kwargs['instance']), 'rules.xml')
            if os.path.exists(rules):
                fp = open(rules)
                kwargs['initial']['rules_editor'] = fp.read()
                fp.close()
            kwargs['initial']['theme_mapper'] = theme_url(kwargs['instance'])
        super(ThemeForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super(ThemeForm, self).save(commit)
        instance.save()  # We need the pk

        if 'upload' in self.files:
            f = self.files['upload']
            if zipfile._check_zipfile(f):
                z = zipfile.ZipFile(f)
                # Unzip uploaded theme
                z.extractall(theme_path(instance))

        path = theme_path(instance)
        if not os.path.exists(path):
            os.makedirs(path)

        rules = os.path.join(theme_path(instance), 'rules.xml')
        fp = open(rules, 'w')
        if self.cleaned_data['rules_editor']:
            fp.write(self.cleaned_data['rules_editor'])
        elif hasattr(settings, 'DIAZO_INITIAL_RULES_FILE') and \
                settings.DIAZO_INITIAL_RULES_FILE and \
                os.path.exists(settings.DIAZO_INITIAL_RULES_FILE):
            init_rules = open(settings.DIAZO_INITIAL_RULES_FILE)
            fp.write(init_rules.read())
        fp.close()

        if instance.enabled:
            for t in Theme.objects.all():
                t.enabled = False
                t.save()
        return instance


class ThemeAdmin(admin.ModelAdmin):
    list_display = ('name', 'enabled',)
    actions = [enable_theme]
    form = ThemeForm

    def get_fieldsets(self, request, obj=None):
        "Hook for specifying fieldsets for the add form."
        upload_classes = ()
        editor_classes = ('collapse',)
        if obj:
            upload_classes = ('collapse',)
            editor_classes = ()

        return (
            (None, {'fields': ('name', 'prefix', 'enabled', 'debug',)}),
            (_('Upload theme'), {'classes': upload_classes, 'fields': ('upload',)}),
            (_('Rules editor'), {'classes': editor_classes, 'fields': ('rules_editor',)}),
            (_('Theme mapper'), {'classes': editor_classes, 'fields': ('theme_mapper',)}),
        )


admin.site.register(Theme, ThemeAdmin)
