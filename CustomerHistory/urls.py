from django.urls import path
from .views import CreateHistoryViewXML, ItemListViewXML

urlpatterns = [
    path('history/', CreateHistoryViewXML.as_view(), name='create_history_xml'),
    path('history/query/', ItemListViewXML.as_view(), name='query_history_xml'),
]