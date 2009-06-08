#!/usr/bin/python
#
# cnb.py - (c) 2007...2009 Matthew J Ernisse <mernisse@ub3rgeek.net>
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
from rrdtool import *
import re
import sys
import os
import mechanize
import urllib2
from urllib2 import HTTPError, URLError

mechanize._urllib2.build_opener(urllib2.HTTPHandler(debuglevel=1))


#
# Your username / password for the online banking website.  This script should
# be owner-readable ONLY because of the cleartext credentials.  The script 
# DOES NOT check, it is up to YOU.
#
USERNAME = ""
PASSWORD = ""

# The challange / response question and answers.  the key is the challange and
# the value is the answer.  Eg:
# 'What is the name of your first employer' : 'your mom',
# this must be a valid python dict assignment
CHALLANGE = {
}

#
# If you simply change BASE to the path to this script, it will be used
# for all the files created / used by this script.  You can customize the 
# files individually if you like.
#
BASE=os.path.dirname(sys.argv[0])
#
# Set your e-mail address here, this goes into the user-agent so your bank
# can e-mail you if they don't like you scraping them.
#
OWNER='mernisse@ub3rgeek.net'

#
# You can setup your proxys here, if you do so, please uncomment the
# proxy block below.
#
proxy = { 
	"https": None,
	"http": None,
	 }

#
# You can change these if you like, though you shouldn't need to.
#
RRD=BASE + "/cnb-balance.rrd"
COOKIE=BASE + "/cnbcookie.txt"

# End User Configuration
host = "cnbsec1.cnbank.com"

start_page = "https://cnbsec1.cnbank.com/CAN_40/Common/SignOn/Start.asp"
landing_page = "https://cnbsec1.cnbank.com/CAN_40/Common/Accounts/Accounts.asp"

if not USERNAME or not PASSWORD or not CHALLANGE or not OWNER:
	print "Please edit this file and follow the directions in the comments"
	print "\n"
	sys.exit(0)

br = mechanize.Browser()
cj = mechanize.LWPCookieJar()

try:
	cj.revert(COOKIE)
except:
	pass

br.addheaders = [ 
	("User-agent", "Mozilla/5.0 (X11; U; i386; " + OWNER + ")"),
	]
#
#if proxy:
#	br.set_proxies(proxy)
#
br.set_cookiejar(cj)
br.set_handle_robots(False)
br.set_handle_refresh(True, 10, True)
br.set_handle_redirect(True)

#
# Debug
#
#br.set_debug_http(True)
#br.set_debug_responses(True)
#br.set_debug_redirects(True)
#logger = logging.getLogger("mechanize")
#logger.addHandler(logging.StreamHandler(sys.stdout))
#logger.setLevel(logging.DEBUG)

try:
	br.open(start_page)
except HTTPError, e:
	print str(e)
	sys.exit(1)

cj.save(COOKIE)
assert br.viewing_html()
br.select_form('form1')
br["SignOnID"] = USERNAME 
br["Password"] = PASSWORD

try:
	r = br.submit()
	cj.save(COOKIE)
except HTTPError, e:
	print str(e)
	sys.exit(1)
except URLError, e:
	print str(e)
	sys.exit(1)

try:
	soup = BeautifulSoup.BeautifulSoup(r.get_data())
except Exception, e:
	print "Caught Exception %s" % ( str(e) )
	print r.get_data()
	sys.exit(1)

question = str(soup.findAll('div', attrs={'class': 'comodotfInput'})[0])
question = re.search(r'Question: (.*)\?', question, re.I).groups()[0]
answer = ''

for k,v in CHALLANGE.iteritems():
	print k
	if re.search(k, question, re.I):
		answer = v
		break
else:
	print "Could not find a match for %s in CHALLANGE." % (question)
	sys.exit(1)

br.select_form(nr=0)
br['answer'] = answer

r = br.submit()

try:
	r = br.open(landing_page)
except HTTPError, e:
	print str(e)
	sys.exit(1)

page = r.get_data()

accounts = []

for balance in re.findall("\$([\d,]+[\d\.]+[\d]{2})", page):
	accounts.append(balance.replace(",",""))

# balance is now  a list of balances	
# The first one is the checking account available balance.

cnb_rrd = RoundRobinDatabase(RRD)

if not os.path.exists(RRD):
	# 1 row per 4 h = 6 rows / day = 2190 rows / year = 6570 / 3y
	cnb_rrd.create(
		DataSource("checking", type=GaugeDST, heartbeat=14400, min='0', max='100000000'),
		RoundRobinArchive(cf=LastCF, xff=0, steps=1, rows=6570),
		step=7200)

cnb_rrd.update(Val(accounts[0]), t=['checking'])
