This document describes how to create initial deployments of a priorities tool on a remote server. 
After the initial deployment, you can use fabric (see `docs/updating.txt`) to update the remote server, 
import datasets, etc.

# If on Ubuntu 14.04 or later
Postgresql 9.3 and later do no support postgis less than 2.0.
Django 1.4 does not support postgis 2.0
Instead, install postgresql 9.2 and postgis 1.5
```
#remove all packages related to postgresql-9.3
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt/ $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
sudo apt-get install wget ca-certificates
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt-get update
sudo apt-get upgrade
sudo apt-get install postgresql-9.2 postgresql-server-dev-9.2
sudo apt-get install build-essential libgeos-c1 libproj-dev libjson-c-dev libxml2-dev libxml2-utils xsltproc docbook-xsl docbook-mathml

#Create a workspace and do the following within it
sudo apt-get install build-essential libgeos-c1 libproj-dev libjson-c-dev libxml2-dev libxml2-utils xsltproc docbook-xsl docbook-mathml

#Instal GEOS
wget http://download.osgeo.org/geos/geos-3.3.8.tar.bz2
tar xjf geos-3.3.8.tar.bz2
cd geos-3.3.8
./configure
make
sudo make install
cd ..

#Install PostGIS 1.5
wget http://download.osgeo.org/postgis/source/postgis-1.5.8.tar.gz
tar xfvz postgis-1.5.8.tar.gz
cd postgis-1.5.8
./configure
make
sudo make install
sudo ldconfig

```

# Install requirements
```
# Note - Postgresql and PostGIS are covered earlier. If using django 1.5 or later you can use apt to get them by adding them to the list below.
sudo apt-get install libpq-dev python-dev git  python-setuptools python-gdal  libcurl4-gnutls-dev libxml2-dev libxslt1-dev libfreetype6-dev
```

# If a fresh Ubuntu Server
```
cd /usr/local/
sudo mkdir apps
sudo chown <uname> apps
cd apps
```

# Checkout the source

```
git clone https://github.com/Ecotrust/juniper-priorities.git <PROJECT_NAME> 
cd <PROJECT_NAME>
git checkout <PROJECT_NAME> 
```

# Install madrona et. al. into virtual environment 

```
sudo apt-get install python-virtualenv
virtualenv --system-site-packages env-<PROJECT_NAME>
source env-<PROJECT_NAME>/bin/activate
cd env-<PROJECT_NAME>
mkdir src
cd src
git clone https://github.com/Ecotrust/madrona.git
cd ../../
pip install -r env-<PROJECT_NAME>/src/madrona/requirements.txt --allow-external elementtree --allow-unverified elementtree
pip install --upgrade --force-reinstall -r requirements.txt --allow-external PIL --allow-unverified PIL
cd env-<PROJECT_NAME>/src/djmapnik
python setup.py build && python setup.py install
pip install mapnik
cd ../madrona
python setup.py install
```

# Create and populate database

```
cd priorities
sudo su - postgres
dropdb <PROJECT_NAME>
createdb <PROJECT_NAME>
createuser -P <DB_USERNAME>

### POSTGIS 1.5 ###

cd <work>/postgis-1.5.8/
psql -d <PROJECT_NAME> -f postgis/postgis.sql
psql -d <PROJECT_NAME> -f spatial_ref_sys.sql

### POSTGIS 2+ ###

psql <PROJECT_NAME>
  CREATE EXTENSION postgis;
  CREATE EXTENSION postgis_topology;
  \q

### END POSTGIS SPATIAL ENABLEMENTIZATION ###

psql
  GRANT ALL PRIVILEGES ON DATABASE <PROJECT_NAME> TO <DB_USERNAME>;
  \q
exit

### If that isn't enough, make DB_USER a superuser
ALTER ROLE <DB_USERNAME> WITH SUPERUSER;

# set up settings_local.py for DB and redis
pip install django-redis-cache msgpack-python==0.1.13
python manage.py syncdb
python manage.py migrate
python manage.py site <FULL_HOST_NAME>
python manage.py enable_sharing --all
python manage.py loaddata fixtures/flatblocks.json
python manage.py loaddata fixtures/project_base_data.json 
```

# Apache

* edit `deploy/wsgi.py`
* edit `deploy/tilestache_wsgi.py`
* create apache vhost file based on the default
```
sed 's/APPNAME/<PROJECT_NAME>/' deploy/default.apache > /etc/apache2/sites-available/<PROJECT_NAME>.labs.ecotrust.org
touch MAINTENANCE_MODE
sudo a2ensite <PROJECT_NAME>.labs.ecotrust.org
sudo /etc/init.d/apache2 reload
```
* Create a `logs/celery.log` file, `chmod 775` it and put it in the `www-data` group.
* Install the `celeryd.init` script according to the instructions in the header

# Next steps

See `docs/updating.txt`
