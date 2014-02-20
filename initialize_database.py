import cPickle
from nsweb.settings import DATA, PICKLE_DATABASE, FEATURE_DATABASE
from nsweb.core import db
from nsweb.models import studies, features

# Re-initialize database
db.drop_all()
db.create_all()

# Read in the study data (contains pickled data originally in the database.txt file)
pickleData = open( DATA + PICKLE_DATABASE,'rb')
dataset = cPickle.load(pickleData)
pickleData.close()

# Create Feature records--just the features themselves, not mapping onto Studies yet
features_text=open(DATA + FEATURE_DATABASE)
feature_dict={}
feature_list = features_text.readline().split()[1:]  # Feature names
for x in feature_list:
    feature_dict[x] = features.Feature(feature=x)
    db.session.add(feature_dict[x])
db.session.commit()

# Store mapping of studies --> features, where values are frequencies
#features_text=map(str.split,features_text.readlines())
feature_data = {}#map( lambda r: map(float,str.split(r)), features_text.readlines())
for x in features_text:
    x=x.split()
    feature_data[int(x[0])] = map(float,x[1:])
features_text.close()
#feature_data=zip(*feature_data)

# Create Study records
n_studies = len(dataset)
for i,x in enumerate(dataset):
    # print "STUDY: ", x.get('id'), "(%d/%d)" % (i+1, n_studies)
    table_num=x.get('table_num')#workaround for empty table_num field
    study = studies.Study(
                          pmid=int(x.get('id')),
                          doi=x.get('doi'),
                          title=x.get('title'),
                          journal=x.get('journal'),
                          space=x.get('space'),
                          authors=x.get('authors'),
                          year=x.get('year'))
    peaks = [map(float, y) for y in x.get('peaks')]
    db.session.add(study)

    # Create Peaks and attach to Studies
    for coordinate in peaks:
        peak=studies.Peak(x=coordinate[0],y=coordinate[1],z=coordinate[2])
        study.peaks.append(peak)
        db.session.add(peak)
    
    # Map features onto studies via a Frequency join table that also stores frequency info
    pmid_frequencies=feature_data[study.pmid]
    for y in range(len(feature_list)):
        if pmid_frequencies[y] > 0.0:
            db.session.add(features.Frequency(study=study,feature=feature_dict[feature_list[y]],frequency=pmid_frequencies[y]))
            feature_dict[feature_list[y]].num_studies+=1
            feature_dict[feature_list[y]].num_activations+=len(peaks)
              
    # Commit each study record separately. A bit slower, but conserves memory.
    db.session.commit()
