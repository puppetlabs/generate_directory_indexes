from __future__ import print_function
import boto3
import jinja2
from jinja2 import Environment
import re
import pytz
from cStringIO import StringIO
import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def lambda_handler(event, context):
    print("lambda_handler started")
    logger.info('got event{}'.format(event))
    #buckets = ['yum.puppetlabs.com', 'apt.puppetlabs.com', 'downloads.puppetlabs.com']
    buckets = ['yum.puppetlabs.com']
    for bucket in buckets:
        generateIndexes(bucket)
    return { 
        'body' : "Finished regenerating directory indexes",
        'statusCode' : 200,
        'headers': {},
        'isBase64Encoded': False
    }

def list_bucket_contents(bucket):
    # Initial setup
    s3 = boto3.resource('s3')
    s3_bucket = s3.Bucket(bucket)

# list objects in bucket
    objects = map(lambda obj:
    { 'name': obj.key,
      'size': obj.size,
      'lastModified': obj.last_modified,
      'icon': 'unknown.gif'
    }, s3_bucket.objects.all())
    filtered_objects = filter(lambda k: not bool(re.match('.*index_by.*\.html$', k['name'])), objects)
    return filtered_objects


# create unique list of prefixes
def prefixes(bucket_contents):
    file_list = map(lambda n: n['name'], bucket_contents)
    prefixes = map(lambda n: '/'.join(n.split('/')[:-1]), file_list)
    unique_prefixes = set(prefixes)
    return list(unique_prefixes)

def list_subdirectories(prefixes, prefix):
    subdirectories = []
    for path in prefixes:
        if path.startswith(prefix):
            suffix = path[len(prefix):]
            suffix = filter(None, suffix.split('/'))

            for subdir in suffix:
                subdirectories.append(subdir)
    unique_subdirs = set(subdirectories)
    return filter(None, list(unique_subdirs))

def directoryLastModified(prefix, bucket_contents):
    filtered = filter(lambda k: k['name'].startswith(prefix) and len(k['name'].split('/')) == len(prefix.split('/')) + 1, bucket_contents)
    # if there are any files in the folder, the last_modified date for the directory
    # is the last_modified date for the newest file in the directory
    if(len(filtered) > 0):
        sorted_bucket_contents = sorted(filtered, key=lambda k: k['lastModified'])
        last_modified = sorted_bucket_contents[-1:][0]['lastModified']
        return last_modified
    # if there aren't any files in the folder, cheat and use current time (dumb hack, I know)
    else:
        from datetime import tzinfo, timedelta, datetime

        ZERO = timedelta(0)

        class UTC(tzinfo):
            def utcoffset(self, dt):
                return ZERO
            def tzname(self, dt):
                return "UTC"
            def dst(self, dt):
                return ZERO

        utc = UTC()
        return datetime.now(utc)

# list files and subdirectories under a given prefix
def ls(prefixes, prefix, bucket_contents):
    filtered_bucket_contents = []
    # list objects under prefix
    for obj in bucket_contents:
        # if obj['name'] starts with the prefix and contains no slashes, add it to the filtered list
        if(obj['name'].startswith(prefix)):
            suffix = obj['name'][len(prefix) + 1:]
            if('/' not in suffix):
                filtered_bucket_contents.append(obj)

    # list directories under prefix
    for subdir in list_subdirectories(prefixes, prefix):
        filtered_bucket_contents.append({
            'name': subdir,
            'size': 0,
            'lastModified': directoryLastModified(subdir, bucket_contents),
            'icon': 'folder.gif'
            })
    
    return filtered_bucket_contents

def sort_bucket_contents(bucket_contents, order_by, reverse_order=False):
    sorted_bucket_contents = sorted(bucket_contents, key=lambda k: k[order_by])

    if(reverse_order):
        sorted_bucket_contents.reverse()

    return sorted_bucket_contents

def index_link(prefix, current_order_by, new_order_by, reverse_order):
    if current_order_by == new_order_by:
        return index_file_name(prefix, current_order_by, not reverse_order)
    else:
        return index_file_name(prefix, new_order_by, False)

# use a templating library to turn a prefix and a list of contents into an HTML directory index
def render_index(prefix, order_by, contents, reverse_order):
    parent_directory = '/'.join(prefix.split('/')[:-1])

    index_by = {}
    index_by['name'] = index_link(prefix, order_by, 'name', reverse_order)
    index_by['size'] = index_link(prefix, order_by, 'size', reverse_order)
    index_by['lastModified'] = index_link(prefix, order_by, 'lastModified', reverse_order)

    HTML = """
    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
    <html>
     <head>
       <title>Index of /{{prefix}}</title>
     </head>
     <body>
       <h1>Index of /{{prefix}}</h1>
    <table><tr><th></th><th><a href="{{index_link['name']}}">Name</a></th><th><a href="{{index_link['lastModified']}}">Last modified</a></th><th><a href="{{index_link['size']}}">Size</a></th><th>Description</th></tr><tr><th colspan="5"><hr></th></tr>
    {% if prefix %}
    <tr><td valign="top"><img src="https://s3-us-west-2.amazonaws.com/icons.puppet.com/back.gif"></td><td><a href="/{{parent_directory}}">Parent Directory</a></td><td>&nbsp;</td><td align="right">  - </td><td>&nbsp;</td></tr>
    {% endif %}
    {% for item in contents %}
        <tr><td valign="top"><img src="https://s3-us-west-2.amazonaws.com/icons.puppet.com/{{item['icon']}}" alt="[DIR]"></td><td><a href="{{item['name'].split('/')[-1:][0]}}">{{item['name'].split('/')[-1:][0]}}</a></td><td align="right">{{item['lastModified']}}  </td><td align="right"> {{item['size']}}</td><td>&nbsp;</td></tr>
    {% endfor %}
    <tr><th colspan="5"><hr></th></tr>
    </table>
    </body></html>
    """

    return Environment().from_string(HTML).render(prefix=prefix, contents=contents, parent_directory=parent_directory, index_link=index_by)

def index_file_name(prefix, order_by, reverse_order):
    order_suffix = "_reverse" if reverse_order else ""
    file_name = 'index' + '_by_' + order_by + order_suffix + '.html'

    return file_name if len(prefix) == 0 else prefix + '/' + file_name

# upload rendered HTML to S3 bucket
def upload_index(bucket, prefix, rendered_html, order_by, reverse_order=False):
    object_name = index_file_name(prefix, order_by, reverse_order)

    s3c = boto3.client('s3')
    fake_handle = StringIO(rendered_html)
    response = s3c.put_object(Bucket=bucket, Key=object_name, Body=fake_handle.read(), ContentType='text/html')
    #print response # TODO: error handling

    return response

def setBucketPermissions(bucket):
    s3 = boto3.resource('s3')
    s3_bucket = s3.Bucket(bucket)
    for obj in s3_bucket.objects.all():
        obj.Acl().put(ACL='public-read')

def configureWebsite(bucket):
    s3 = boto3.client('s3')
    website_configuration = { 'IndexDocument': {'Suffix': 'index_by_name.html' } }
    s3.put_bucket_website(Bucket=bucket, WebsiteConfiguration=website_configuration)

def generateIndexes(bucket):
    logger.info('started GenerateIndexes for {}'.format(bucket))

    # get bucket contents
    bucket_contents = list_bucket_contents(bucket)
    # create list of unique prefixes
    unique_prefixes = prefixes(bucket_contents)
    # iterate over list of unique prefixes
    for prefix in unique_prefixes:
        contents = ls(unique_prefixes, prefix, bucket_contents)

        for order_by in ['name', 'size', 'lastModified']:
            for reverse_order in [True, False]:
                logger.info('processing prefix {}'.format(prefix))
                ordered_contents = sort_bucket_contents(contents, order_by, reverse_order)
                rendered_html = render_index(prefix, order_by, ordered_contents, reverse_order)
                upload_index(bucket, prefix, rendered_html, order_by, reverse_order)
    setBucketPermissions(bucket)
    configureWebsite(bucket)
    return True
