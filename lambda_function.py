from __future__ import print_function
import boto3
import jinja2
from jinja2 import Environment
import re
import pytz
from concurrent import futures
import collections
from timeit import default_timer as timer # performance profiling

# Python 2/3 compatible hack
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

import logging
logger = logging.getLogger(__name__)
boto3_logger = logging.getLogger('boto3')
botocore_logger = logging.getLogger('botocore')
logging.basicConfig(level=logging.DEBUG)
boto3_logger.setLevel(logging.WARN)
botocore_logger.setLevel(logging.WARN)

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

def scan_bucket(bucket):
    # Initial setup
    s3 = boto3.resource('s3')
    s3_bucket = s3.Bucket(bucket)

    objects = {}
    unique_prefixes = set([])
    bucket = collections.namedtuple('bucket', ['objects', 'prefixes'])([], set([]))

    for obj in s3_bucket.objects.all():
        # Ignore the index files we generate
        if bool(re.match('.*index_by.*\.html$', obj.key)):
            continue
        # Get only the object data we care about
        bucket.objects.append({ 'name': obj.key,
                             'size': obj.size,
                             'lastModified': obj.last_modified,
                             'icon': 'unknown.gif'
        })
        # Generate a list of unique prefixes while enumerating to avoid having to enumerate bucket contents again later
        bucket.prefixes.add('/'.join(obj.key.split('/')[:-1]))
    return bucket

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
    filtered_contents = list(filter(lambda k: k['name'].startswith(prefix) and len(k['name'].split('/')) == len(prefix.split('/')) + 1, bucket_contents))
    # if there are any files in the folder, the last_modified date for the directory
    # is the last_modified date for the newest file in the directory
    if(len(filtered_contents) > 0):
        sorted_bucket_contents = sorted(filtered_contents, key=lambda k: k['lastModified'])
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
def upload_index(client, bucket, prefix, rendered_html, order_by, reverse_order=False):
    object_name = index_file_name(prefix, order_by, reverse_order)

    #s3c = boto3.client('s3')
    fake_handle = StringIO(rendered_html)
    response = client.put_object(Bucket=bucket, Key=object_name, Body=fake_handle.read(), ContentType='text/html')
#    print(response)# TODO: error handling

    return response

def configureWebsite(bucket):
    s3 = boto3.client('s3')
    website_configuration = { 'IndexDocument': {'Suffix': 'index_by_name.html' } }
    s3.put_bucket_website(Bucket=bucket, WebsiteConfiguration=website_configuration)

def patch_http_connection_pool(**constructor_kwargs):
    # http://stackoverflow.com/questions/18466079/can-i-change-the-connection-pool-size-for-pythons-requests-module
    """
    This allows to override the default parameters of the 
    HTTPConnectionPool constructor.
    For example, to increase the poolsize to fix problems 
    with "HttpConnectionPool is full, discarding connection"
    call this function with maxsize=16 (or whatever size 
    you want to give to the connection pool)
    """
    from urllib3 import connectionpool, poolmanager

    class MyHTTPConnectionPool(connectionpool.HTTPConnectionPool):
        def __init__(self, *args,**kwargs):
            kwargs.update(constructor_kwargs)
            super(MyHTTPConnectionPool, self).__init__(*args,**kwargs)
    poolmanager.pool_classes_by_scheme['http'] = MyHTTPConnectionPool

#patch_http_connection_pool(maxsize=25)
#generateIndexes('downloads.puppetlabs.com')
#generateIndexes('yum.puppetlabs.com')
#generateIndexes('apt.puppetlabs.com')


# Reorganization

# Step 2: generate, render indexes

# Step 3: upload indexes
#print('number of indexes to generate: {}'.format(len(indexes_to_generate)))

def create_index_queue(bucket):
    start = timer()
    for prefix in bucket.prefixes:
        #print("prefix: ", prefix)
        contents = ls(bucket.prefixes, prefix, bucket.objects)

        indexes_to_generate = []
        for order_by in ['name', 'size', 'lastModified']:
            for reverse_order in [True, False]:
                #logger.info('processing prefix {}'.format(prefix))
                ordered_contents = sort_bucket_contents(bucket.objects, order_by, reverse_order)
                indexes_to_generate += [{'prefix': prefix, 'ordered_contents': ordered_contents, 'order_by': order_by, 'reverse_order': reverse_order}]
    end = timer()
    print("generating indexes list took ", end - start)
    return indexes_to_generate
    #print('number of indexes to generate: {}'.format(len(indexes_to_generate)))

def render_indexes(index_queue):
    return map(lambda obj: {
        'prefix': obj['prefix'],
        'order_by': obj['order_by'],
        'reverse_order': obj['reverse_order'],
        'rendered_html': render_index(obj['prefix'], obj['order_by'], obj['ordered_contents'], obj['reverse_order'])
    }, index_queue)

def upload_indexes(rendered_indexes, bucket_name):
    start = timer()
    client = boto3.client('s3')
    with futures.ThreadPoolExecutor(max_workers=20) as executor:
        todo = []
        for i in rendered_indexes:
            future = executor.submit(upload_index, client, bucket_name, i['prefix'], i['rendered_html'], i['order_by'], i['reverse_order'])
            todo.append(future)
        results = []
        for future in futures.as_completed(todo):
            res = future.result()
            results.append(res)

    end = timer()
    print("uploading indexes took ", end - start)

def index(bucket_name):
    logger.info('started GenerateIndexes for {}'.format(bucket_name))

    # Step 1: enumerate bucket, generate unique prefixes
    start = timer()
    bucket = scan_bucket(bucket_name)
    end = timer()
    print("scanning bucket took ", end - start)


    # Step 2: Figure out which indexes to generate
    start = timer()
    index_queue = create_index_queue(bucket)
    end = timer()
    print("generating index_queue took ", end - start)

    # Step 3: render indexes
    start = timer()
    rendered_indexes = render_indexes(index_queue)
    end = timer()
    print("rendering indexes list took ", end - start)

    start = timer()
    upload_indexes(rendered_indexes, bucket_name)
    end = timer()
    print("uploading indexes took ", end - start)

    configureWebsite(bucket_name)
    return True


index('apt.puppetlabs.com')
#index('directory-index-test')
