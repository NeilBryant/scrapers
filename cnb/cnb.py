#!/usr/bin/python -tt
#
# cnb.py - (c) 2007 - 2012 Matthew J Ernisse <mernisse@ub3rgeek.net>
#
# Redistribution and use in source and binary forms, 
# with or without modification, are permitted provided 
# that the following conditions are met:
#
#    * Redistributions of source code must retain the 
#      above copyright notice, this list of conditions 
#      and the following disclaimer.
#    * Redistributions in binary form must reproduce 
#      the above copyright notice, this list of conditions 
#      and the following disclaimer in the documentation 
#      and/or other materials provided with the distribution.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS 
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT 
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS 
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE 
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, 
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, 
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS 
# OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND 
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR 
# TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE 
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# scrape the Canandaigua National Bank and Trust online banking for balance
# and insert into an RRD for graphing.

import BeautifulSoup
import logging
import re
import sys
import time
import os
import mechanize
import urllib2
from urllib2 import HTTPError, URLError

mechanize._urllib2.build_opener(urllib2.HTTPHandler(debuglevel=1))


#
# ======================================================================== 
# Beginning of user configuration.
# ======================================================================== 
#

#
# Your username / password for the online banking website.  This script should
# be owner-readable ONLY because of the cleartext credentials.  The script 
# DOES NOT check, it is up to YOU.
#
USERNAME = ''
PASSWORD = ''

#
# The new CNBank Online Banking system sets a magic cookie to identify your
# browser.  The autnetication method requires a two-factor code so you will
# need to fetch the cookie from your browser and update this dict with the
# information.
#
COOKIE = {
	'name': '',
	'value': '',
}

#
# This needs to be set to th EXACT user-agent string used to generate this cookie.
# The webpage fingerprints your browser with a Flash application and if you don't
# run the fingerprint app it appears to fall back to user-agent checking.
#
USERAGENT = ''

#
# If you simply change BASE to the path to this script, it will be used
# for all the files created / used by this script.  You can customize the 
# files individually if you like.
#
BASE=''

#
# If you wish to enable debug output, change this to True.
#
DEBUG=None

#
# You can setup your proxys here, if you do so, please uncomment the
# proxy block below.
#
proxy = { 
	'https': '',
	'http': '',
}

#
# If you set RRD, this will try to use the rrd.py lib to update a RRD
# with the information.
#
RRD=''

#
# TODO: support TAB output.
#
TAB=''

#
# ======================================================================== 
# End of user configuration.
# ======================================================================== 
#

if RRD:
	try:
		from rrd import *
	except ImportError:
		print 'E: RRD is set and rrd module not imported successfully.'
		sys.exit(1)

start_page = "https://online.cnbank.com/CNB_Online/Authentication/Login.aspx"

if not USERNAME \
	or not PASSWORD \
	or not COOKIE['name'] \
	or not COOKIE['value'] \
	or not USERAGENT:
	print 'Please edit this file and follow the directions in the comments.'
	sys.exit(1)

br = mechanize.Browser()

cj = mechanize.CookieJar()
cj.set_cookie(mechanize.Cookie(
	None,
	COOKIE['name'], COOKIE['value'], None, False,
	'online.cnbank.com', True, True, 
	'/', True, True, int(time.time()) + 86400, False, None, None, None
))

br.addheaders = [ 
	('User-agent', USERAGENT)
]


if proxy['http'] and proxy['https']:
	if DEBUG:
		print 'Setting Proxy.'
	br.set_proxies(proxy)


br.set_cookiejar(cj)
br.set_handle_robots(False)
br.set_handle_refresh(True, 10, True)
br.set_handle_redirect(True)

#
# Debug
#
if DEBUG == True:
	br.set_debug_http(True)
	br.set_debug_responses(True)
	br.set_debug_redirects(True)
	logger = logging.getLogger("mechanize")
	logger.addHandler(logging.StreamHandler(sys.stdout))
	logger.setLevel(logging.DEBUG)

try:
	if DEBUG:
		print 'I: Trying to open ', start_page

	br.open(start_page)
except HTTPError, e:
	print str(e)
	sys.exit(1)

assert br.viewing_html()
br.select_form('q2online')

forms = list(br.forms())
forms[0].set_all_readonly(False)

br["q2oLoginID"] = USERNAME 
br["q2oPassword"] = PASSWORD
br["_action"] = "submit"
br['q2_1'] = ''
br['q2_2'] = ''

try:
	if DEBUG:
		print ' ===== Trying to submit login form ====='

	r = br.submit()

	if DEBUG:
		print ' ===== End login form ====='
	
except (HTTPError, URLError),  e:
	print 'E: Failed submitting login form: ', str(e)
	sys.exit(1)

try:
	soup = BeautifulSoup.BeautifulSoup(r.get_data())
except Exception, e:
	print 'E: Caught exception: ', str(e)
	print r.get_data()
	sys.exit(1)


# 
# <td class="c3"> is the Available Balance column.
# <td class="c4"> is the Current Balance column.
#
balances = []

try:
	for v in soup.findAll('td', attrs={'class': 'c3'}):
		balances.append(re.sub(r'[$,]', '', v.string))
except Exception, e:
	print 'E: Exception parsing balances: ', str(e)
	sys.exit(1)

#
# balances is now a list of balances, one for each account and the last for your total.
#

if DEBUG:
	print balances

#
# XXX: TODO - support TAB output.
#
if not RRD:
	sys.exit(0)

cnb_rrd = RoundRobinDatabase(RRD)

if not os.path.exists(RRD):
	# 1 row per 4 h = 6 rows / day = 2190 rows / year = 6570 / 3y
	cnb_rrd.create(
		DataSource("checking", type=GaugeDST, heartbeat=14400, min='0', max='100000000'),
		RoundRobinArchive(cf=LastCF, xff=0, steps=1, rows=6570),
		step=7200)

try:
	cnb_rrd.update(Val(balances[0]), t=['checking'])
except Exception, e:
	print 'E: Could not update RRD: ', str(e)

