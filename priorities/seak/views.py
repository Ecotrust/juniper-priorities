from madrona.common.utils import get_logger
# from madrona.shapes.views import ShpResponder
from shapes.views import ShpResponder
from madrona.layer_manager.models import Layer, Theme
#from madrona.features.views import get_object_for_viewing
from django.http import HttpResponse
from django.template.defaultfilters import slugify
from django.contrib.gis.geos import MultiPolygon
from django.shortcuts import render_to_response
from django.views.decorators.cache import cache_page, cache_control
from django.conf import settings
from django.template import RequestContext
from seak.models import PlanningUnit
from models import PuVsCost
import TileStache 
import os
import json
import time
import tempfile

logger = get_logger()

def welcome(request, template_name='common/welcome.html', extra_context=None):
    """
    Welcome window
    """
    if not extra_context:
        extra_context = {}

    context = RequestContext(request, {})
    context.update(extra_context)
    return render_to_response(template_name, context)

def map(request, template_name='common/map_ext.html', extra_context=None):
    """
    Main application window
    """
    if not extra_context:
        extra_context = {}
        
    extra_context['js_opts_json'] = json.dumps(settings.JS_OPTS)

    context = RequestContext(request, {
        'api_key': settings.GOOGLE_API_KEY, 
        'session_key': request.session.session_key,
    })
    context.update(extra_context)
    return render_to_response(template_name, context)

def about(request, template_name='news/about.html', extra_context=None):
    """
    Learn More Page
    """
    if not extra_context:
        extra_context={}

    themes = []
    for theme_obj in Theme.objects.all():
        theme = theme_obj.toDict
        theme_dict = {}
        if not theme['layers'] == []:
            print "%s: %s" % (theme['display_name'], str(theme['layers']))
            theme_dict['name'] = theme['display_name']
            theme_dict['description'] = theme['description']
            theme_dict['layers'] = []
            for layer in theme['layers']:
                layer_obj = Layer.objects.get(id=layer)
                layer_dict = layer_obj.toDict
                layer_dict['metadata'] = layer_obj.metadata_link
                theme_dict['layers'].append(layer_dict)
            themes.append(theme_dict)

    context = RequestContext(request, {
        'themes': themes
        })
    context.update(extra_context)
    return render_to_response(template_name, context)    

def watershed_shapefile(request, instances):
    from seak.models import PlanningUnitShapes, Scenario, PuVsAux
    wshds = PlanningUnit.objects.all()
    wshd_fids = [x.fid for x in PlanningUnit.objects.all()]
    results = {}
    for fid in wshd_fids:
        w = wshds.get(fid=fid)
        p = w.geometry
        if p.geom_type == 'Polygon':
            p = MultiPolygon(p)
        results[fid] = {'pu': w, 'geometry': p, 'name': w.name, 'hits': 0, 'bests': 0} 

        for puAux in PuVsAux.objects.filter(pu=w):
            results[fid][puAux.aux.dbf_fieldname] = puAux.amount

    stamp = int(time.time() * 1000.0)

    for instance in instances:
        viewable, response = instance.is_viewable(request.user)
        if not viewable:
            return response
        if not isinstance(instance, Scenario):
            return HttpResponse("Shapefile export for prioritization scenarios only", status=500)

        ob = json.loads(instance.output_best)
        wids = [int(x.strip()) for x in ob['best']]
        puc = json.loads(instance.output_pu_count)

        for fid in wshd_fids:
            # Calculate hits and best
            try:
                hits = puc[str(fid)] 
            except KeyError:
                hits = 0
            best = fid in wids
            results[fid]['hits'] += hits
            if best:
                results[fid]['bests'] += 1

    readme = """Prioritization Scenario Array
contact: mperry@ecotrust.org

Includes scenarios:
    %s

    'bests' contains the number of scenarios in which the subbasin was included in the best run
    'hits' contains the number of times the subbasin was included in any run, cumulative across scenarios.
    """ % ('\n    '.join([i.name for i in instances]), )

    for fid in results.keys():
        r = results[fid]
        # PlanningUnitShapes.objects.create(stamp=stamp, fid=fid, **r)
        PlanningUnitShapes.objects.create(stamp=stamp, fid=fid, geometry=r['geometry'], bests=r['bests'], hits=r['hits'], pu=r['pu'], name=r['name'])
        

    allpus = PlanningUnitShapes.objects.filter(stamp=stamp)
    for newPu in allpus:
        r = results[newPu.fid]
        for key in r:
            setattr(newPu, key, r[key])

    shp_response = ShpResponder(allpus, readme=readme)
    filename = '_'.join([slugify(i.pk) for i in instances])
    shp_response.file_name = slugify('scenarios_' + filename)

    addl_cols = [x.aux.dbf_fieldname for x in PuVsAux.objects.filter(pu=allpus[0].pu)]

    return shp_response(addl_cols)

def watershed_marxan(request, instance):
    from seak.models import Scenario
    viewable, response = instance.is_viewable(request.user)
    if not viewable:
        return response

    if not isinstance(instance, Scenario):
        return HttpResponse("Shapefile export for watershed prioritizations only", status=500)

    from madrona.common.utils import KMZUtil
    zu = KMZUtil()
    filename = os.path.join(tempfile.gettempdir(), 
            '%s_%s.zip' % (slugify(instance.name),slugify(instance.date_modified)))
    directory = instance.outdir 
    zu.toZip(directory, filename)

    fh = open(filename,'rb')
    zip_stream = fh.read() 
    fh.close()
    response = HttpResponse()
    response['Content-Disposition'] = 'attachment; filename=Marxan_%s.zip' % slugify(instance.name)
    response['Content-length'] = str(len(zip_stream))
    response['Content-Type'] = 'application/zip'
    response.write(zip_stream)
    return response

@cache_page(settings.CACHE_TIMEOUT)
@cache_control(must_revalidate=False, max_age=settings.CACHE_TIMEOUT)
def planning_units_geojson(request):
    def get_feature_json(geom_json, prop_json):
        return """{
            "type": "Feature",
            "geometry": %s, 
            "properties": %s
        }""" % (geom_json, prop_json)

    feature_jsons = []
    for pu in PlanningUnit.objects.all():
        cf_values = dict([(x.cf.dbf_fieldname, x.amount) for x in pu.puvscf_set.all()])

        fgj = get_feature_json(pu.geometry.json, json.dumps(
            {'name': pu.name, 
             'fid': pu.fid, 
             'cf_fields': pu.conservation_feature_fields,
             'cf_values': cf_values,
             'cost_fields': pu.cost_fields,
             'area': pu.area}
        )) 
        feature_jsons.append(fgj)

    geojson = """{ 
      "type": "FeatureCollection",
      "features": [ %s ]
    }""" % (', \n'.join(feature_jsons),)

    return HttpResponse(geojson, content_type='application/json')

from django.views.decorators.cache import never_cache
# set headers to disable all client-side caching
@never_cache
def user_scenarios_geojson(request):
    from seak.models import Scenario

    # Why not use @login_required? 
    # That just redirects instead of giving proper Http Response code of 401
    user = request.user
    if user.is_anonymous() or not user.is_authenticated:
        return HttpResponse("You must be logged in to view your scenarios.", status=401)

    scenarios = Scenario.objects.filter(user=user).order_by('-date_modified')

    geojson = """{ 
      "type": "FeatureCollection",
      "features": [ %s ]
    }""" % (', \n'.join([s.geojson(None) for s in scenarios]),)

    return HttpResponse(geojson, content_type='application/json')

@never_cache
def shared_scenarios_geojson(request):
    from seak.models import Scenario

    # Why not use @login_required? 
    # That just redirects instead of giving proper Http Response code of 401
    user = request.user
    if user.is_anonymous() or not user.is_authenticated:
        return HttpResponse("You must be logged in to view your scenarios.", status=401)

    scenarios = Scenario.objects.shared_with_user(user).exclude(user=user).order_by('-date_modified')

    geojson = """{ 
      "type": "FeatureCollection",
      "features": [ %s ]
    }""" % (', \n'.join([s.geojson(None) for s in scenarios]),)

    return HttpResponse(geojson, content_type='application/json')

@cache_page(settings.CACHE_TIMEOUT)
@cache_control(must_revalidate=False, max_age=settings.CACHE_TIMEOUT)
def tiles(request):
    path_info = request.path_info.replace('/tiles', '')
    (mimestr, bytestotal) = TileStache.requestHandler(config_hint=settings.TILE_CONFIG, 
            path_info=path_info, query_string=None)
    return HttpResponse(bytestotal, content_type=mimestr)


@cache_page(settings.CACHE_TIMEOUT)
@cache_control(must_revalidate=False, max_age=settings.CACHE_TIMEOUT)
def field_lookup(request):
    from seak.models import Cost, ConservationFeature
    from flatblocks.models import FlatBlock
    try:
        constraint_text = FlatBlock.objects.get(slug="constraints").content
    except:
        constraint_text = "Constraints"
    flut = {}
    for c in Cost.objects.all():
        units_txt = ""
        if c.units:
            units_txt = " (%s)" % c.units
        flut[c.dbf_fieldname] = "%s%s" % (c.name, units_txt)
    for c in ConservationFeature.objects.all():
        units_txt = ""
        if c.units:
            units_txt = " (%s)" % c.units
        flut[c.dbf_fieldname] = "%s%s" % (c.name, units_txt)
    return HttpResponse(json.dumps(flut), content_type='application/json')

@cache_page(settings.CACHE_TIMEOUT)
@cache_control(must_revalidate=False, max_age=settings.CACHE_TIMEOUT)
def id_lookup(request):
    from seak.models import ConservationFeature
    flut = {}
    for c in ConservationFeature.objects.all():
        flut[c.id_string] = c.dbf_fieldname
    return HttpResponse(json.dumps(flut), content_type='application/json')
