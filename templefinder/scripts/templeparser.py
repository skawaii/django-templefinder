#!/usr/local/bin/python
import requests, unicodedata
from lxml import html


WP_BASE_URL = 'https://en.wikipedia.org'
WP_TEMPLES_URL = WP_BASE_URL + '/wiki/List_of_temples_of_The_Church_of_Jesus_Christ_of_Latter-day_Saints'
LDS_URL = 'https://www.lds.org/church/temples/%s?lang=eng'
XPATH_EXP = {'operating': './/span[@id="Operating"]/..',
             'upcoming': './/span[@id="Under_construction"]/..',
             'announced': './/span[@id="Announced"]/..',
             'tr_vcard': './/tr[@class="vcard"]',
             'name_link': './/b/span/a',
             # some of the announced temples don't yet have an <a> tag for the name
             'name_span': './/b/span',
             'image_page_link': './/a[@class="image"]',
             'image_link': './/div[@class="fullImageLink"]/a',
             'addr_details': './/div[@id="address-section"]/ul[@class="details-section"]',
             # sometimes the address is in <div id="contact-section">
             'addr_details2': './/div[@id="contact-section"]/ul[@class="details-section"]',
             'addr_divs': './/div[@class="three-column"]',
             'notice': './/div[@class="three-column-notice"]',
             'physical_addr': './/li',
             'mailing_addr': './/ul[@class="mailing-spacer"]/li',
             'phone_fax': './/li',
             'phone_fax2': './ul[last()]/li',
            }


def parse_wikipedia(vcard):
  ''' Parse the temple name and image link from the <tr class="vcard"> elements.
      Returns a dict with name and image_link keys. image_link values will be 
      None if there is no availble temple image on the Wikipedia page.
  '''
  data = {}

  # parse the name
  try:
    name = vcard.find(XPATH_EXP['name_link']).get('title')
  except AttributeError:
    # some of the names for the announced temples aren't linked yet, so we have
    # to get the name from the <span> tag instead
    name = vcard.find(XPATH_EXP['name_span']).text

  data['name'] = name.split(' Temple')[0] if name.endswith(' Temple') else name

  # parse out the link to the image file page, which contains the link to the actual image
  image_page_link = vcard.find(XPATH_EXP['image_page_link'])

  if image_page_link is None:
    data['image_link'] = None
  else:
    tree = html.fromstring(requests.get(WP_BASE_URL + image_page_link.get('href')).text)
    data['image_link'] = 'http:' + tree.find(XPATH_EXP['image_link']).get('href')

  return data


def parse_lds(name):
  '''
  '''
  name = name.lower().replace(' ', '-').replace('.', '').replace("'", '')

  # handle non-ascii characters (not allowed in URLs)
  if isinstance(name, unicode): name = replace_diacritics(name)

  # special cases for LDS URLs that don't follow the normal pattern
  if name == 'provo-city-center': name = 'new-provo-temple-provo-tabernacle'
  elif name == 'fort-collins-colorado': name = 'fort-collins-colorado-temple'
  elif name == 'meridian-idaho': name = 'meridian-idaho-temple'
  elif name == 'winnipeg-manitoba': name = 'winnipeg-manitoba-temple'
  elif name == 'kinshasa-democratic-republic-of-the-congo': name = 'kinshasa-democratic-republic-of-congo'
  elif name == 'rio-de-janeiro-brazil': name = 'rio-de-janiero-brazil'

  tree = html.fromstring(requests.get(LDS_URL % name).text)
  data = {}

  data['address'] = parse_lds_address(tree)

  return data


def parse_lds_address(tree):
  '''
  '''
  data = {}
  addr_details = tree.find(XPATH_EXP['addr_details'])

  # for those special address sections inside a <div id="contact-section"> elem
  if addr_details is None: addr_details = tree.find(XPATH_EXP['addr_details2'])

  # most of the under construction and announced temples have nothing in their address sections
  if addr_details is not None:
    addr_divs = addr_details.xpath(XPATH_EXP['addr_divs'])

    # there can be [0-3] addr_divs:
    #  0 - no address info at all
    #  1 - just the physical address
    #  2 - physical and mailing addresses in separate divs, but telephone is in the same div
    #      as the mailing address. The 3rd div is a notice.
    #  3 - pyhical address, mailing address, telephone in separate divs
    data['physical_addr'] = None
    data['mailing_addr'] = None
    data['notice'] = None

    if len(addr_divs) > 0: data['physical_addr'] = [li.text for li in addr_divs[0].findall(XPATH_EXP['physical_addr'])]

    if len(addr_divs) > 1:
      div = addr_divs[1]
      data['mailing_addr'] = [li.text for li in div.findall(XPATH_EXP['mailing_addr'])]

      if len(addr_divs) > 2: phone_fax = addr_divs[2].findall(XPATH_EXP['phone_fax'])
      else: phone_fax = div.findall(XPATH_EXP['phone_fax2'])

      data['phone'] = phone_fax[0].text if len(phone_fax) > 0 else None
      data['fax'] = phone_fax[1].text.lstrip('Facsimile: ') if len(phone_fax) > 1 else None

  return data


def replace_diacritics(input_str):
  ''' http://stackoverflow.com/a/517974 '''
  nkfd_form = unicodedata.normalize('NFKD', input_str)
  return u''.join([c for c in nkfd_form if not unicodedata.combining(c)])


if __name__ == '__main__':
  # parse the operating, under construction, and announced temples from Wikipedia
  response = requests.get(WP_TEMPLES_URL)
  tree = html.fromstring(response.text)

  # get the operating temples
  print 'Operating\n------------------'
  operating = []

  # XXX not DRY. move into a function
  for elem in tree.find(XPATH_EXP['operating']).itersiblings():
    if elem.tag == 'h3': break

    if elem.tag == 'table':
      for vcard in elem.xpath(XPATH_EXP['tr_vcard']):
        data = parse_wikipedia(vcard)
        data.update(parse_lds(data['name'])) # parse further data about each temple from lds.org
        print data

        operating.append(data)

  print 'operating count: %d\n' % len(operating)

  # get the temples under construction
  print 'under construction\n------------------'
  under_construction = []

  for elem in tree.find(XPATH_EXP['upcoming']).itersiblings():
    if elem.tag == 'h3': break

    if elem.tag == 'table':
      for vcard in elem.xpath(XPATH_EXP['tr_vcard']):
        data = parse_wikipedia(vcard)
        data.update(parse_lds(data['name'])) # parse further data about each temple from lds.org
        print data
        under_construction.append(data)

  print 'Under Construction Count: %d\n' % len(under_construction)

  # get the announced temples
  print 'Announced\n------------------'
  announced = []

  for elem in tree.find(XPATH_EXP['announced']).itersiblings():
    if elem.tag == 'h3': break

    if elem.tag == 'table':
      for vcard in elem.xpath(XPATH_EXP['tr_vcard']):
        data = parse_wikipedia(vcard)
        data.update(parse_lds(data['name'])) # parse further data about each temple from lds.org
        print data
        announced.append(data)

  print 'Announced Count: %d' % len(announced)

