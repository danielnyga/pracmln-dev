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
    this.offset = 100;

    this['barChartSVG'+ this.id] = d3.select("#" + this.id).append("svg")
              .attr("class", "chart")
              .attr("width", "100%")
              .attr("height", "100%")
              .append("g")
              .attr("transform", "translate(" + 100 + "," + 20 + ")");

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
        this.h = this.barChartData.length * this.barHeight + 2.5*this.offset;

        var format = d3.format(".4f");
        var x = d3.scale.linear()
            .range([0, this.w-120])
            .domain([0,1]);

        var y = d3.scale.ordinal()
            .rangeRoundBands([0, this.h], .1)
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
            .attr("dx", function(d) { return d.value > .1 ? -3 : "3.5em"; })
            .attr("dy", ".35em")
            .attr("text-anchor", "end")
            .text(function(d) { return format(d.value); });

        // remove elements
        barSelection.exit().remove();

        this['barChartSVG'+ this.id].selectAll("g.y.axis")
            .call(yAxis);

        this['barChartSVG'+ this.id].selectAll("g.x.axis")
            .call(xAxis);

        d3.select("#" + this.id).select("svg").attr("height", this.h);
    }
  }
});
