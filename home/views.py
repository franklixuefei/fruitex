from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.template import Context, loader
from home.models import Store, Item
import json
from category import category
from django.views.decorators.csrf import csrf_exempt
import re
from django.db.models import Q

TAX_RATE = 0.13

labels = {
  'Produce': 'cate_label_produce.png',
  'Home & Lifestyle': 'cate_label_home.png',
  'Groceries': 'cate_label_grocery.png',
  'Snacks & Candies': 'cate_label_candy.png',
  'Beverages':'cate_label_beverage.png',
  'Pet Care':'cate_label_pet.png',
  'Department A-E': 'cate_label_book.png',
  'Department F-J': 'cate_label_book.png',
  'Department K-O': 'cate_label_book.png',
  'Department P-Z': 'cate_label_book.png',
}

def getStore(request):
  if 'query' in request.GET:
    stores,_ = extractStore(request.GET['query'])
    if len(stores) > 0 and stores[0] in category:
      return stores[0]
  return 'sobeys'

@csrf_exempt
def main(request):
    template = loader.get_template('home.html')
    context = Context({
      'category' : json.dumps(category[getStore(request)]),
      'labels' : json.dumps(labels)
      })
    return HttpResponse(template.render(context))

def getItemPrice(it):
  if it.sales_price > 0:
    return it.sales_price
  return it.price

def toStructuredItem(it):
  return {'name' : it.name, 'price' : getItemPrice(it), 'category' : it.category,
      'id' : it.id, 'tax_class' : it.tax_class, 'sku' : it.sku, 'store': it.store.name,
      'remark': it.remark}

def extractCate(query):
  patterns = ["cate:'([^']*)'", "cate:([^ ]*)",]
  cate = []
  r = query
  for p in patterns:
    cate.extend(re.findall(p, r))
    r = re.sub(p, '', r)
  return cate, r

def extractStore(query):
  patterns = ["store:([^ ]*)",]
  store = []
  r = query
  for p in patterns:
    store.extend(re.findall(p, r))
    r = re.sub(p, '', r)
  return store, r

def getRawItemsByQuery(query):
  cates,query = extractCate(query)
  stores,query = extractStore(query)
  if cates:
    cate = cates[0]
  else:
    cate = ''
  if stores:
    store = stores[0]
  else:
    store = ''
  keyword = re.sub(r'^\s*|\s*$', '', query)
  res = Item.objects.all().filter(store__name__icontains=store).filter(category__icontains=cate)
  for k in keyword.split():
    res = res.filter(Q(name__icontains=k+' ') | Q(name__icontains=' '+k) | Q(remark__icontains='"%s"' % k))
  return res.exclude(out_of_stock=1)

def getItemsByRange(query, startId, num):
  return map(toStructuredItem, getRawItemsByQuery(query)[startId : startId + num])

def getPopularItemsByRange(query, startId, num):
  return map(toStructuredItem, getRawItemsByQuery(query).order_by('-sold_number')[startId : startId + num])

def getItemsByIds(ids):
  return map(toStructuredItem, Item.objects.filter(id__in = set(ids)))

def computeTax(item):
  if item['tax_class'] == 'zero-rate':
    return 0
  elif item['tax_class'] == 'standard-rate':
    return TAX_RATE * item['price']
  else:
    return 0

def computeDelivery(item):
  return 4.0

import urllib2

def getItemsInternal(request, getItemCallback):
  if request.method == 'POST':
    if 'startId' in request.POST:
      query = request.POST['query']
      query = urllib2.unquote(query.encode("utf8"))
      startId = int(request.POST['startId'])
      num = int(request.POST['num'])
      return HttpResponse(json.dumps(getItemCallback(query, startId, num)))
    elif 'ids' in request.POST:
      ids = json.loads(request.POST['ids'])
      return HttpResponse(json.dumps(getItemsByIds(ids)))
    else:
      return HttpResponse('error')
  else:
    return HttpResponse('error')

@csrf_exempt
def getItems(request):
  return getItemsInternal(request, getItemsByRange)

@csrf_exempt
def getPopularItems(request):
  return getItemsInternal(request, getPopularItemsByRange)

def computeSummaryInternal(idsStr):
    ids = json.loads(idsStr)
    items = getItemsByIds(ids)
    d = computeDelivery(items)
    s = 0.0
    t = 0.0
    for item in items:
      ct = ids.count(item['id'])
      s += item['price'] * ct
      t += computeTax(item) * ct
    return {'sum' : s, 'tax' : t, 'delivery' : d, 'total' : s + t + d}

@csrf_exempt
def computeSummary(request):
  if request.method == 'POST':
    res = computeSummaryInternal(request.POST['ids'])
    return HttpResponse(json.dumps(res))
  else:
    return HttpResponse('error')
