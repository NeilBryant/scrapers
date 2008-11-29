#!/usr/bin/python -tt
#
# $Id: tmobile.py,v 1.1 2008/10/15 00:34:55 mernisse Exp $
#
# tmobile.py - (c) 2008 Matthew J Ernisse <mernisse@ub3rgeek.net>
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
# scrape the t-Mobile online account manager for minute and text message
# balances and insert into an RRD for graphing.

import mechanize
import os
import re
import sys
import BeautifulSoup

from rrdtool import *
from urllib2 import Request, urlopen
from ClientForm import HiddenControl

#
# Configuration Section
#
# MOBILE is you 10 digit t-mobile US telephone number
#
MOBILE=""
#
# this is your my.t-mobile.com password for the above 
# mobile number
#
PASSWORD=""
#
# this is where to store the rrd output file
#
RRD = ""
#
# End of configuration section
#
start_page = "https://my.t-mobile.com/login/MyTmobileLogin.aspx"
landing_page = "https://my.t-mobile.com/billing/"
minutes_page = "https://ebill.t-mobile.com/myTMobile/onMinutesUsedLinkClick.do"

br = mechanize.Browser()

br.set_handle_robots(False)
br.set_handle_refresh(True, 10, True)
br.set_handle_redirect(True)

#
# Debug
#
#import logging
#br.set_debug_http(True)
#br.set_debug_responses(True)
#br.set_debug_redirects(True)
#logger = logging.getLogger("mechanize")
#logger.addHandler(logging.StreamHandler(sys.stdout))
#logger.setLevel(logging.DEBUG)

try:
	br.open(start_page)
except HTTPError, e:
	sys.exit("%d: %s" % (e.code, e.msg))

assert br.viewing_html()
# 
# build the form, this is done by JavaScript on the actual live site.  The
# form onClick handler sets __EVENTTARGET and __EVENTARGUMENT.
# 
br.select_form('Form1')
form = list(br.forms())[0]
et = HiddenControl('hidden', '__EVENTTARGET', {'value': 'Login1$btnLoginClickOnce'})
ea = HiddenControl('hidden', '__EVENTARGUMENT', {'value': ''})

form.controls.append(et)
form.controls.append(ea)

br["Login1:txtMSISDN"] = MOBILE
br["Login1:txtPassword"] = PASSWORD

try:
	r = br.submit()
except HTTPError, e:
	sys.exit("%d: %s" % (e.code, e.msg))

#
# fetch the landing page, this is done by a sneaky javascript bit, if you don't
# do this, then it 302's you to the logout and kills your session.
#
try:
	r = br.open(landing_page)
except HTTPError, e:
	sys.exit("%d: %s" % (e.code, e.msg))

#
# now fetch the minutes page
#
try:
	r = br.open(minutes_page)
except HTTPError, e:
	sys.exit("%d: %s" % (e.code, e.msg))

try:
        soup = BeautifulSoup.BeautifulSoup(r.get_data())
except Exception, e:
        print "Caught Exception %s" % ( str(e) )
        print r.get_data()
        sys.exit(1)

balances = { "text": "0", "minutes": "0" }

table = soup.find('table', attrs={"id": "UnbilledSummary.MinutesUsedSummary"})
rows = table.findAll('tr', attrs={"class":"data_row"})

for row in rows:
	td = row.findAll('td')
	if td[0].contents[0] == "Text Messages":
		balances['text'] = float(td[5].contents[0])
	elif td[0].contents[0] == "Incl Minutes":
		balances['minutes'] = float(td[5].contents[0])

rrd = RoundRobinDatabase(RRD)
if not os.path.exists(RRD):
        rrd.create(
                DataSource("minutes", type=GaugeDST, heartbeat=14400, min=0, max=1000000000),
                DataSource("text", type=GaugeDST, heartbeat=14400, min=0, max=1000000000),
                RoundRobinArchive(cf=LastCF, xff=0, steps=1, rows=6570),
                step=7200)

rrd.update(Val(balances['minutes'], balances['text']), 
	t=["minutes", "text"])

