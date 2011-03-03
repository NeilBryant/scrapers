#!/usr/bin/python
#
# amex.py - (c) 2008-2011 Matthew J Ernisse <mernisse@ub3rgeek.net>
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
from rrd import *
from urllib2 import HTTPError

#
# Your username / password for the online banking website.  This script should
# be owner-readable ONLY because of the cleartext credentials.  The script 
# DOES NOT check, it is up to YOU.
#
USERNAME = ''
PASSWORD = ''

#
# If you simply change BASE to the path to this script, it will be used
# for all the files created / used by this script.  You can customize the 
# files individually if you like.
#
BASE=''

#
# Set AMEX_TAB if you want to write a tab file down.
#
AMEX_TAB=None

#
# Set your e-mail address here, this goes into the user-agent so your bank
# can e-mail you if they don't like you scraping them.
#
OWNER=''


DEBUG=None
#DEBUG=True

#
# You can setup your proxys here, if you do so, please uncomment the
# proxy block below.
#
proxy = { 
	"https": "",
	"http": "",
	 }

#
# You can change these if you like, though you shouldn't need to.
#
RRD=BASE + "/amex-balance.rrd"
COOKIE=BASE + "/amexcookie.txt"

# End User Configuration
host = "home.americanexpress.com"

start_page = "https://%s/home/mt_personal_cm.shtml" % (host)
action_page = "https://www99.americanexpress.com/myca/logon/us/action?request_type=LogLogonHandler&location=us_pre1_cards";
dest_page = "https://online.americanexpress.com/myca/acctsumm/us/action?request_type=authreg_acctAccountSummary&entry_point=lnk_homepage&aexp_nav=sc_checkbill&referrer=ushome&section=login";


if not USERNAME or not PASSWORD:
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
	("User-agent", "Mozilla/5.0 (X11; U; Linux i686; en-US; rv 1.0) %s" %
	               (OWNER)),
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

cj.save(COOKIE)
assert br.viewing_html()
br.select_form('ssoform')
br["UserID"] = USERNAME 
br["Password"] = PASSWORD

# this is done in javascript by amex's website, so let's sneak it in here.
forms = list(br.forms())
forms[1].set_all_readonly(False)
forms[1].action = action_page
br["DestPage"] = dest_page
br["UserID"] = USERNAME 
br["Password"] = PASSWORD

try:
	if DEBUG:
		print "Trying to submit login form"

	r = br.submit()
#	cj.save(COOKIE)
except HTTPError, e:
	sys.exit("%d: %s" % (e.code, e.msg))


try:
	soup = BeautifulSoup.BeautifulSoup(r.get_data())
except Exception, e:
	print "Caught Exception %s" % ( str(e) )
	print r.get_data()
	sys.exit(1)

balances =  soup.findAll('div', attrs={"class" : "NGBODY3VALUE" })
balance = balances[3].string.strip().replace("$", "").replace(",", "")

if not balance:
	sys.exit(1)

if AMEX_TAB:
	fd = open(AMEX_TAB, "w")
	fd.write("%s\n" % ( balance ))
	fd.close()
	sys.exit(0)

rrd = RoundRobinDatabase(RRD)

if not os.path.exists(RRD):
	# 1 row per 4 h = 6 rows / day = 2190 rows / year = 6570 / 3y
	rrd.create(
		DataSource("balance", type=GaugeDST, heartbeat=14400, min='0', max='100000000'),
		RoundRobinArchive(cf=LastCF, xff=0, steps=1, rows=6570),
		step=7200)
try:
	rrd.update(Val(balance), t=['balance'])
except Exception, e:
	print "Cannot update RRD, %s" % (str(e))

