#!/usr/bin/env python
#
# Wrapper module for rrdtool
#
#
# Copyright 2006, Red Hat, Inc
# Mihai Ibanescu <misa@redhat.com>
#
# This software may be freely redistributed under the terms of the
# Lesser GNU general public license.
#
# You should have received a copy of the Lesser GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.
#

# Id: rrd.py 101964 2006-09-08 02:55:53Z misa

"""
This module is a wrapper for the python bindings for rrdtool (the round
robin database).

How to create an rrd database:

r = RoundRobinDatabase("iostats.rrd")
heartbeat = 1200
r.create(
    DataSource("tps", type=GaugeDST, heartbeat=heartbeat),
    DataSource("rtps", type=GaugeDST, heartbeat=heartbeat),
    DataSource("wtps", type=GaugeDST, heartbeat=heartbeat),
    RoundRobinArchive(cf=AverageCF, xff=0.5, steps=1, rows=1200),
    RoundRobinArchive(cf=AverageCF, xff=0.5, steps=12, rows=2400),
    start=-864000, step=600)

How to update an rrd database:
r = RoundRobinDatabase("iostats.rrd")
r.update(Val(1, 1), template=('rtps', 'wtps'))
r.update(Val(1, 1, timestamp=time.time() - 3600), template=('rtps', 'wtps'))

How to graph:
g = RoundRobinGraph("iostats.png")
g.graph(
    Def("tps", "iostats.rrd", data_source="tps", cf=AverageCF),
    Def("rtps", "iostats.rrd", data_source="rtps", cf=AverageCF),
    Def("wtps", "iostats.rrd", data_source="wtps", cf=AverageCF),
    LINE1("tps", rrggbb="ff0000", legend="tps"),
    LINE1("rtps", rrggbb="00ff00", legend="rtps"),
    LINE1("wtps", rrggbb="0000ff", legend="wtps"),
    alt_y_mrtg=None,
    width=900,
    height=200,
    x="HOUR:1:HOUR:2:HOUR:4:0:%H",
    title="IO stats",
    start=(time.time() - 86400),
    end=(time.time() - 3600),
)
"""

import os
from rrdtool import create, error, fetch, graph, info, last, resize, tune, update
from types import ListType, TupleType

__all__ = [
    'create', 'error', 'fetch', 'graph', 'info', 'last', 'resize',
    'tune', 'update',
    'BasicType', 'DataSourceType',
    'GaugeDST', 'CounterDST', 'DeriveDST', 'AbsoluteDST',
    'ConsolidationFunction', 'AverageCF', 'MinCF', 'MaxCF', 'LastCF',
    'SpecializedConsolidationFunction', 'HWPredictCF', 'SeasonalCF',
    'DevseasonalCF', 'DevpredictCF', 'FailuresCF',
    'Val', 'GraphType', 'TimeUnitType',
    'SECOND', 'MINUTE', 'HOUR', 'DAY', 'WEEK', 'MONTH', 'YEAR',
    'RoundRobinDatabase', 'RoundRobinGraph', 'Def', 'Graph',
    'HRULE', 'VRULE', 'LINE1', 'LINE2', 'LINE3', 'AREA', 'STACK',
    'PRINT', 'GPRINT', 'COMMENT',
    'DataSource', 'RoundRobinArchive',
    'XAxis',
]

class BasicType:
    "Base type class"
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

    def __repr__(self):
        return '<%s instance; string repr="%s">' % (self.__class__.__name__, self.name)

class DataSourceType(BasicType):
    "Class that describes a DST"
    pass

GaugeDST = DataSourceType('GAUGE')
CounterDST = DataSourceType('COUNTER')
DeriveDST = DataSourceType('DERIVE')
AbsoluteDST = DataSourceType('ABSOLUTE')

class ConsolidationFunction(BasicType):
    "Class that describes a CF"
    pass

AverageCF = ConsolidationFunction('AVERAGE')
MinCF = ConsolidationFunction('MIN')
MaxCF = ConsolidationFunction('MAX')
LastCF = ConsolidationFunction('LAST')

class SpecializedConsolidationFunction(ConsolidationFunction):
    "Class that describes a specialized CF"
    pass

HWPredictCF = SpecializedConsolidationFunction('HWPREDICT')
SeasonalCF = SpecializedConsolidationFunction('SEASONAL')
DevseasonalCF = SpecializedConsolidationFunction('DEVSEASONAL')
DevpredictCF = SpecializedConsolidationFunction('DEVPREDICT')
FailuresCF = SpecializedConsolidationFunction('FAILURES')

class Val:
    """Class that describes an RRD value
    To init: Val(1, 2, 3), Val(1, 2, 3, timestamp=time.time() - 3600)
    """
    def __init__(self, *args, **kwargs):
        if kwargs:
            if len(kwargs.keys()) > 1:
                raise ValueError, "Val only accepts one keyword, timestamp"
            k = kwargs.keys()[0]
            valid = ('timestamp', 'ts')
            if k not in valid:
                raise ValueError, "Unknown keyword %s" % k
            self.timestamp = int(kwargs[k])
        else:
            self.timestamp = 'N'

        self.vals = args

    def __str__(self):
        return "%s:%s" % (self.timestamp, str.join(':', map(str, self.vals)))

    def __len__(self):
        return len(self.vals)

class GraphType(BasicType):
    "Class that describes a graph type"
    pass

_Hrule = GraphType("HRULE")
_Vrule = GraphType("VRULE")
_Line1 = GraphType("LINE1")
_Line2 = GraphType("LINE2")
_Line3 = GraphType("LINE3")
_Area = GraphType("AREA")
_Stack = GraphType("STACK")
_Print = GraphType("PRINT")
_GPrint = GraphType("GPRINT")
_Comment = GraphType("COMMENT")

class TimeUnitType(BasicType):
    "Class that describes a time unit type"
    pass

SECOND = TimeUnitType("SECOND")
MINUTE = TimeUnitType("MINUTE")
HOUR = TimeUnitType("HOUR")
DAY = TimeUnitType("DAY")
WEEK = TimeUnitType("WEEK")
MONTH = TimeUnitType("MONTH")
YEAR = TimeUnitType("YEAR")

class RoundRobinDatabase:
    """
    A Round Robin Database

    The constructor takes the rrd name which is subsequently applied to all
    the functions that deal with an rrd
    """
    def __init__(self, rrd_name):
        self._rrd_name = rrd_name

    # Wrappers around RRD's functions

    def create(self, *args, **kwargs):
        "Same as rrdtool create"
        args = [self._rrd_name] + map(str, args)
        for k, v in kwargs.items():
            args.append("--%s" % k)
            args.append(str(v))
        #print "DEBUG: rrdtool create", " ".join(args)
        return create(*args)

    def update(self, *args, **kwargs):
        "Same as rrdtool update"
        self._sanity()
        if kwargs:
            if len(kwargs.keys()) > 1:
                raise ValueError, "only accepts one keyword, template"
            k = kwargs.keys()[0]
            valid = ('template', 't')
            if k not in valid:
                raise ValueError, "Unknown keyword %s" % k

            val = kwargs[k]
            if type(val) not in [ListType, TupleType]:
                raise ValueError, "Invalid type for template value"

            template = val
            valnum = len(template)
        else:
            template = None
            valnum = None

        # Sanity check: all the entries have the same number of values
        for a in args:
            if not isinstance(a, Val):
                raise ValueError, "Not a Val instance"
            if not valnum:
                valnum = len(a)
                continue
            if len(a) != valnum:
                raise ValueError, "Number of values does not match"

        args = [self._rrd_name] + map(str, args)
        if template:
            args = ['--template', str.join(':', template)] + args

        #print "DEBUG: rrdtool update", " ".join(args)
        return update(*args)

    def last(self):
        "Same as rrdtool last"
        self._sanity()
        return last(self._rrd_name)

    # Housekeeping functions
    def exists(self):
        return os.path.exists(self._rrd_name)

    def get_name(self):
        return self._rrd_name

    def _sanity(self):
        if not self.exists():
            raise OSError, "Could not open file %s" % self._rrd_name

class RoundRobinGraph:
    "A grapher class for a Round Robin Database"
    def __init__(self, filename):
        self._filename = filename

    def graph(self, *args, **kwargs):
        "Same as rrdtool graph"
        args = [self._filename] + map(str, args)
        for k, v in kwargs.items():
            args.append("--%s" % k.replace("_", "-"))
            if v is not None:
                args.append(str(v))
        return graph(*args)

class Def:
    "Helper class for building DEF values"
    def __init__(self, name, rrd, data_source=None, cf=None):
        if not os.path.isfile(rrd):
            raise OSError, "Could not open file %s" % rrd

        self._rrd = rrd
        self._name = name
        if data_source is None:
            # By default, same as the name
            data_source = self._name
        self._data_source = data_source
        if cf is None:
            raise ValueError, "Consolidation function not specified"
        if not isinstance(cf, ConsolidationFunction):
            raise ValueError, "%s not a valid consolidation function" % cf
        self._cf = cf

    def __str__(self):
        return "DEF:%s=%s:%s:%s" % (self._name, self._rrd, self._data_source,
            self._cf)
    
class Graph:
    "Base graph class"
    def __init__(self, graph_type=None, name=None, rrggbb=None, legend=None,
                optional_color=None):
        if rrggbb is None and not optional_color:
            raise ValueError, "Colors not defined"
        if name is None:
            raise ValueError, "Name not defined"
        if graph_type is None:
            raise ValueError, "Graph type not defined"
        if not isinstance(graph_type, GraphType):
            raise ValueError, "Invalid graph type %s" % graph_type
        self._graph_type = graph_type
        self._name = name
        self._rrggbb = rrggbb
        self._legend = legend
        self._optional_color = optional_color

    def __str__(self):
        if self._optional_color and self._rrggbb is None:
            rest = ""
        else:
            if self._rrggbb:
                rrggbb = "#%s" % self._rrggbb
            else:
                rrggbb = ""
            if self._legend:
                legend = ":%s" % self._legend
            else:
                legend = ""
            rest = "%s%s" % (rrggbb, legend)
        return "%s:%s%s" % (self._graph_type, self._name, rest)

class HRULE(Graph):
    "HRULE class"
    def __init__(self, name, rrggbb=None, legend=None):
        Graph.__init__(self, name=name, graph_type=_Hrule, rrggbb=rrggbb,
            legend=legend)

class VRULE(Graph):
    "VRULE class"
    def __init__(self, name, rrggbb=None, legend=None):
        Graph.__init__(self, name=name, graph_type=_Vrule, rrggbb=rrggbb,
            legend=legend)

class LINE1(Graph):
    "LINE1 class"
    def __init__(self, name, rrggbb=None, legend=None):
        Graph.__init__(self, name=name, graph_type=_Line1, rrggbb=rrggbb,
            legend=legend, optional_color=1)

class LINE2(Graph):
    "LINE2 class"
    def __init__(self, name, rrggbb=None, legend=None):
        Graph.__init__(self, name=name, graph_type=_Line2, rrggbb=rrggbb,
            legend=legend, optional_color=1)

class LINE3(Graph):
    "LINE3 class"
    def __init__(self, name, rrggbb=None, legend=None):
        Graph.__init__(self, name=name, graph_type=_Line3, rrggbb=rrggbb,
            legend=legend, optional_color=1)

class AREA(Graph):
    "AREA class"
    def __init__(self, name, rrggbb=None, legend=None):
        Graph.__init__(self, name=name, graph_type=_Area, rrggbb=rrggbb,
            legend=legend, optional_color=1)

class STACK(Graph):
    "STACK class"
    def __init__(self, name, rrggbb=None, legend=None):
        Graph.__init__(self, name=name, graph_type=_Stack, rrggbb=rrggbb,
            legend=legend, optional_color=1)

class PRINT(Graph):
    "PRINT class"
    _graph_type = _Print
    def __init__(self, name, cf=None, format=None):
        self._name = name
        if cf is None:
            raise ValueError, "Missing Consolidation Function"
        self._cf = cf
        if format is None:
            raise ValueError, "Missing format"
        self._format = format

    def __str__(self):
        return "%s:%s:%s:%s" % (self._graph_type, self._name,
            self._cf, self._format)

class GPRINT(PRINT):
    "GPRINT class"
    _graph_type = _GPrint

class COMMENT(Graph):
    "COMMENT class"
    _graph_type = _Comment
    def __init__(self, text):
        self._text = text

    def __str__(self):
        return "%s:%s" % (self._graph_type, self._text)

class DataSource:
    "Class for DS"
    def __init__(self, name, type=None, heartbeat=300, min=None, max=None):
        self.name = name
        self.heartbeat = heartbeat

        if type is None:
            raise ValueError, "No Data Source Type specified"

        if not isinstance(type, DataSourceType):
            raise ValueError, "Data Source Type not an instance of DataSourceType"

        self.type = type
        
        if min is None:
            self.min = 'U'
        else:
            self.min = int(min)
        
        if max is None:
            self.max = 'U'
        else:
            self.max = int(max)

    def __str__(self):
        return "DS:%s:%s:%s:%s:%s" % (self.name, self.type, self.heartbeat,
            self.min, self.max)

class RoundRobinArchive:
    "Class for RRA"
    def __init__(self, cf=None, xff=None, steps=None, rows=None):
        if cf is None:
            raise ValueError, "No Consolidation Function specified"

        if not isinstance(cf, ConsolidationFunction):
            raise ValueError, "Consolidation Function not an instance of ConsolidationFunction"

        self.cf = cf
        
        if xff is None:
            raise ValueError, "xfiles factor not defined"

        self.xff = float(xff)

        if steps is None:
            raise ValueError, "steps not defined"

        self.steps = int(steps)

        if rows is None:
            raise ValueError, "rows not defined"

        self.rows = int(rows)
        
    def __str__(self):
        return "RRA:%s:%.2f:%s:%s" % (self.cf, self.xff, self.steps, self.rows)

class XAxis:
    "Class for the x-axis"
    def __init__(self, **kwargs):
        if not kwargs:
            # No option specified
            self.no_grid = 1
            return
        self.no_grid = 0
        self.keywords = ['base_grid', 'major_grid', 'label']
        unit_keywords = map(lambda x: x + "_unit", self.keywords)
        delta_keywords = map(lambda x: x + "_delta", self.keywords)
        precision_keywords = ['label_precision']
        strftime_keywords = ['label_strftime']

        # Start processing keywords
        for k in unit_keywords:
            if not kwargs.has_key(k) or kwargs[k] is None:
                raise ValueError, "Missing value for keyword %s" % k

            val = kwargs[k]
            if not isinstance(val, TimeUnitType):
                raise ValueError(
                    "Wrong value for keyword %s, expected TimeUnitType" % k)

            setattr(self, k, val)
            del kwargs[k]

        for k in delta_keywords + precision_keywords:
            if not kwargs.has_key(k) or kwargs[k] is None:
                raise ValueError, "Missing value for keyword %s" % k

            val = kwargs[k]
            try:
                val = int(val)
            except ValueError:
                raise ValueError(
                    "Incorrect value %s for keyword %s, expected int" % (val, k))
            setattr(self, k, val)
            del kwargs[k]

        for k in strftime_keywords:
            if not kwargs.has_key(k) or kwargs[k] is None:
                val = "%X"
            else:
                val = kwargs[k]

            setattr(self, k, val)
            if kwargs.has_key(k): del kwargs[k]

        # If more keywords, raise exception
        if kwargs:
            raise ValueError("Unknown keywords %s; supported keywords %s" %
                (kwargs.keys(), unit_keywords + delta_keywords +
                    precision_keywords + strftime_keywords))

    def __str__(self):
        if self.no_grid:
            return "none"
        values = map(lambda x, h=self: getattr(h, x),
            reduce(lambda a, b: a + b,
                map(lambda x: ["%s_unit" % x, "%s_delta" % x], self.keywords)) +
                    ["label_precision", "label_strftime"])

        return str.join(':', map(str, values))
