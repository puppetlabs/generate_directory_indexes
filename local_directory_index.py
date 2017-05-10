#!/usr/bin/env python
import jinja2
from jinja2 import Environment
import os,sys
import datetime
import argparse
import re
import logging

# Python 2/3 compatible hack
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

#sys.setrecursionlimit(2100000000)

parser = argparse.ArgumentParser()
parser.add_argument("path", help="Path to index and write indexes to")
parser.add_argument("--noop", help="Only print files to be created without writing them to disk", action="store_true")
parser.add_argument('--verbose', '-v', help="Verbose output. Repeat (up to -vvv) for more verbosity", action='count')
args = parser.parse_args()

logger = logging.getLogger(__name__)
if args.verbose == None:
    logging.basicConfig(level=logging.ERROR)
if args.verbose == 1:
    logging.basicConfig(level=logging.WARNING)
elif args.verbose == 2:
    logging.basicConfig(level=logging.INFO)
elif args.verbose >= 3:
    logging.basicConfig(level=logging.DEBUG)

logger.info("info")
logger.error("error")
logger.warning("warning")
logger.debug("debug")

exit()

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

    sorted_contents = sorted(contents, key=lambda k: k[order_by], reverse=reverse_order)
    formatted_contents = format_directory_listing(sorted_contents)

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
    <tr><td valign="top"><img src="https://s3-us-west-2.amazonaws.com/icons.puppet.com/back.gif"></td><td><a href="/{{parent_directory}}/index_by_name.html">Parent Directory</a></td><td>&nbsp;</td><td align="right">  - </td><td>&nbsp;</td></tr>
    {% endif %}
    {% for item in contents %}
        <tr><td valign="top"><img src="https://s3-us-west-2.amazonaws.com/icons.puppet.com/{{item['icon']}}" alt="[DIR]"></td><td><a href="{{item['name'].split('/')[-1:][0]}}">{{item['name'].split('/')[-1:][0]}}</a></td><td align="right">{{item['lastModified']}}  </td><td align="right"> {{item['size']}}</td><td>&nbsp;</td></tr>
    {% endfor %}
    <tr><th colspan="5"><hr></th></tr>
    </table>
    </body></html>
    """

    return Environment().from_string(HTML).render(prefix=prefix, contents=formatted_contents, parent_directory=parent_directory, index_link=index_by)

def index_file_name(prefix, order_by, reverse_order):
    order_suffix = "_reverse" if reverse_order else ""
    file_name = 'index' + '_by_' + order_by + order_suffix + '.html'
    return file_name if len(prefix) == 0 else prefix + '/' + file_name


def format_date(d):
    return datetime.datetime.fromtimestamp(
        int(d)
    ).strftime('%Y-%m-%d %H:%M:%S')

def format_size(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

def generate_indexes():
    indexes_to_generate = []
    for order_by in ['name', 'size', 'lastModified']:
        for reverse_order in [True, False]:
            indexes_to_generate.append({'prefix': prefix, 'contents': contents, 'order_by': order_by, 'reverse_order': reverse_order})

# not in use
def format_directory_listing(directory_listing):
    out = []
    for k in directory_listing:
        out.append ({
        'name': k['name'],
        'lastModified': format_date(k['lastModified']),
        'size': format_size(k['size'])
    })
    return out

def walk(path):
    contents = os.listdir(path)
    directory_listing = []
    errors = []
    # generate indexes for current path
    for file in contents:
        # add size, lastModified, file/folder type to metadata
        fullpath = os.path.join(path, file)
        if bool(re.match('.*index_by.*\.html$', file)):
            continue
        if(os.path.exists(fullpath)):
            directory_listing.append({
                'name': file,
                'lastModified': os.path.getmtime(fullpath),
                'size': os.path.getsize(fullpath)
            })
        else:
            print('skipping \'{}\' because the file cannot be read'.format(fullpath))
    for order_by in ['name', 'size', 'lastModified']:
        for reverse_order in [True, False]:
            file_name = os.path.join(path, index_file_name('', order_by, reverse_order))
            rendered_html = render_index(path, order_by, directory_listing, reverse_order)
            if args.test:
                print('Would create: ', file_name)
            else:
                if args.verbose:
                    print('Wrote: ', file_name)
                index_file = open(file_name, 'w')
                index_file.write(rendered_html)
                index_file.close()


    # recurse into subdirectories
    for file in contents:
        file_pwd = os.path.join(path, file)
        if os.path.isdir(file_pwd):
            walk(file_pwd)

def validate_input(path):
    if not os.path.isdir(path):
        sys.exit('Error: {} is not a directory'.format(path))

validate_input(args.path)
walk(args.path)
