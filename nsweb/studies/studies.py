from nsweb.core import apimanager
from nsweb.models import Study

apimanager().create_api(Study,
                   methods=['GET'],
                   collection_name='studies',
                   results_per_page=20,
                   max_results_per_page=100,)
