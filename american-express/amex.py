#!/usr/bin/python
#
# amex.py - (c) 2008-2013 Matthew J Ernisse <mernisse@ub3rgeek.net>
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
# scrape the American Express online banking site for balance information
# on an AMEX Blue(tm) card and insert into an RRD for graphing.

import logging
import re
import sys
import os
import mechanize

import BeautifulSoup
from getopt import getopt, GetoptError
from urllib2 import HTTPError

#
# You can setup your proxys here, if you do so, please uncomment the
# proxy block below.
#
proxy = { 
	'https': '',
	'http': '',
}
# End User Configuration

DEBUG = None
OWNER = ''
RRD = ''
TAB = ''

# These must be set.
USERNAME = ''
PASSWORD = ''

def Usage():
	print 'American Express account balance scraper'
	print "Usage: %s [-dh] [-r file] [-t file] -o email" % (
		os.path.basename(sys.argv[0])
	)
	print
	print ' -d				turn on debug mode'
	print ' -h 				display this usage and exit'
	print ' -o email			specify the owner\'s e-mail address'
	print ' -r file				update this rrd file'
	print ' -t file 			update this tab file'
	print
	print ' You can setup HTTP/HTTPS proxies by editing the script file'
	sys.exit(0)

try:
	options, arguments = getopt(sys.argv[1:], 'dho:r:t:')
except GetoptError, e:
	print str(e)
	Usage()
	sys.exit(1)

if not options:
	Usage()

for opts, args in options:
	if opts == '-d':
		DEBUG = True
	elif opts == '-h':
		Usage()
	elif opts == '-o':
		OWNER = args
	elif opts == '-r':
		RRD = args
	elif opts == '-t':
		TAB = args

if not USERNAME or not PASSWORD or not OWNER:
	Usage()

if RRD:
	try:
		from rrd import *
	except ImportError:
		print 'E: RRD set, yet failed importing rrd.py'
		sys.exit(1)

start_page = 'https://www.americanexpress.com/'
action_page = 'https://online.americanexpress.com/myca/logon/us/action?request_type=LogLogonHandler&location=us_pre1_cards'
dest_page = 'https://online.americanexpress.com/myca/acctsumm/us/action?request_type=authreg_acctAccountSummary&entry_point=lnk_homepage&aexp_nav=sc_checkbill&referrer=ushome&section=login'

br = mechanize.Browser()

br.addheaders = [ 
	("User-agent", "Mozilla/5.0 (X11; U; Linux i686; en-US; rv 1.0) %s" %
	               (OWNER)),
	]

if proxy['http'] or proxy['https']:
	br.set_proxies(proxy)

br.set_handle_robots(False)
br.set_handle_refresh(True, 30, True)
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
		print "Trying to open %s" % (start_page)

	br.open(start_page)
except HTTPError, e:
	sys.exit("%d: %s" % (e.code, e.msg))

assert br.viewing_html()
br.select_form('ssoform')
br["UserID"] = USERNAME 
br["Password"] = PASSWORD

# this is done in javascript by amex's website, so let's sneak it in here.
forms = list(br.forms())
forms[1].set_all_readonly(False)
forms[1].action = action_page
br["DestPage"] = dest_page
br["USERID"] = USERNAME 
br["PWD"] = PASSWORD

try:
	if DEBUG:
		print "Trying to submit login form"

	r = br.submit()
except HTTPError, e:
	sys.exit("%d: %s" % (e.code, e.msg))

# Amex's page is all javascripted up now, so lets try the mobile
try:
	if DEBUG:
		print "Trying to fetch mobile page"

	r = br.open("https://online.americanexpress.com/myca/mobl/us/CardList.do")

except HTTPError, e:
	sys.exit("%d: %s" % (e.code, e.msg))

try:
	soup = BeautifulSoup.BeautifulSoup(r.get_data())
	balances =  soup.findAll('dl', attrs={
		"id" : "cd"
	})[0].findAll('dt')


	balance = balances[5].string.strip()
	balance = re.search(r'\$([0-9,\.]+)', balance, re.I)
	balance = balance.group(0)
	balance = balance.replace("$", "").replace(",", "")
except Exception, e:
	print 'E: Could not parse balance.  Has the page changed? (%s)' % str(e)
	sys.exit(1)

if not balance:
	print 'E: balance ended up unset.  Has the page changed?'
	sys.exit(1)

if TAB:
	try:
		fd = open(TAB, "w")
		fd.write("%s\n" % ( balance ))
		fd.close()
	except Exception, e:
		print 'E: Could not write TAB file: ', str(e)
		sys.exit(1)

if not RRD:
	sys.exit(0)

rrd = RoundRobinDatabase(RRD)

if not os.path.exists(RRD):
	try:
		# 1 row per 4 h = 6 rows / day = 2190 rows / year = 6570 / 3y
		rrd.create(
			DataSource(
				"balance",
				type=GaugeDST,
				heartbeat=14400,
				min='0',
				max='100000000'
			),
		RoundRobinArchive(
			cf=LastCF,
			xff=0,
			steps=1,
			rows=6570
		),
		step=7200)
	except Exception, e:
		print 'E: Could not create %s, %s.' % (
			RRD,
			str(e)
		)
		sys.exit(1)
try:
	rrd.update(Val(balance), t=['balance'])
except Exception, e:
	print "Cannot update RRD, %s" % (str(e))
