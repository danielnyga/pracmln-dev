/* ************************************************************************

   Copyright:

   License:

   Authors: Mareike Picklum

************************************************************************ */

/**
 * This is the main application class of your custom application "webmln"
 *
 * @asset(webmln/*)
 */
qx.Class.define("webmln.BarChart",
{
  extend : qx.ui.core.Widget,

  /*
  *****************************************************************************
     MEMBERS
  *****************************************************************************
  */
  construct: function(id) {

    this.w = document.getElementById(id, true, true).offsetWidth;
    this.h = document.getElementById(id, true, true).offsetHeight;
    this.id = id;
    this.barHeight = 15;
    this.topOffset = 15;

    this.fontpixels = 7.5; //x-small
    this.yBarWidth = 0;

    this['barChartSVG'+ this.id] = d3.select("#" + this.id).append("svg")
              .attr("class", "chart")
              .append("g")
              .attr("transform", "translate(" + this.yBarWidth + "," + this.topOffset + ")");

    this['barChartSVG'+ this.id].append("g")
        .attr("class", "x axis");

    this['barChartSVG'+ this.id].append("g")
        .attr("class", "y axis");

    this.barChartData = [];
    this.update();
  },

  members :
  {

    /**
     * updates data set for bar chart
     */
    replaceData : function (results) {
        this.clear();
        this.barChartData = results.slice();
        this.barChartData.sort(function(a, b) { return b.value - a.value; });
        var l = [];
        for (var e = 0; e < this.barChartData.length; e++) {
            l.push(this.barChartData[e].name);
        }
        if (l.length > 0) {
            this.yBarWidth = l.reduce(function (a, b) { return a.length > b.length ? a : b; }).length * this.fontpixels;
        }
        this.update();
    },

    /**
     * clear bar chart by emptying data
     */
    clear : function() {
      this.barChartData.splice(0, this.barChartData.length);
      this.update();
    },

    /**
     * redraws the bar chart with the updated data
     */
    update : function () {
        this.h = this.barChartData.length * 1.2 * this.barHeight;
        d3.select("#" + this.id).select("svg").select("g")
            .attr("transform", "translate(" + this.yBarWidth + "," + this.topOffset + ")");

        var format = d3.format(".4f");
        var x = d3.scale.linear()
            .range([0, this.w - this.yBarWidth - 5*this.fontpixels])
            .domain([0, 1]);

        var y = d3.scale.ordinal()
            .rangeRoundBands([0, this.h], .2)
            .domain(this.barChartData.map(function(d) { return d.name; }));

        var xAxis = d3.svg.axis()
            .scale(x)
            .orient("top")
            .tickSize(-this.h);

        var yAxis = d3.svg.axis()
            .scale(y)
            .orient("left")
            .tickSize(1);

        // selection for bars
        var barSelection = this['barChartSVG'+ this.id].selectAll("g.bar")
            .data(this.barChartData,function(d) { return d.name; });

        // create elements (bars)
        var barItems = barSelection.enter()
            .append("g")
            .attr("class", "bar")
            .attr("transform", function(d) { return "translate(0," + y(d.name) + ")"; });

        // create bars and texts
        barItems.append("rect")
            .attr("width", function(d) { return x(d.value); })
            .attr("height", this.barHeight);

        barItems.append("text")
            .attr("class", "value")
            .attr("x", function(d) { return x(d.value); })
            .attr("y", y.rangeBand() / 2)
            .attr("dx", function(d) { return d.value > .1 ? -3 : "4em"; })
            .attr("dy", ".35em")
            .attr("text-anchor", "end")
            .text(function(d) { return format(d.value); });

        // remove elements
        barSelection.exit().remove();

        this['barChartSVG'+ this.id].selectAll("g.y.axis")
            .call(yAxis);

        this['barChartSVG'+ this.id].selectAll("g.x.axis")
            .call(xAxis);

        this.h = this.barChartData.length * 1.2 * this.barHeight + this.topOffset;

        d3.select("#" + this.id).select("svg").select("g")
            .attr("height", this.h)
            .attr("width", this.w);

        d3.select("#" + this.id).select("svg")
            .attr("height", this.h)
            .attr("width", this.w);
    }
  }
});
