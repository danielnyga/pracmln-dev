/* ************************************************************************
   Copyright:
   License:
   Authors:
************************************************************************ */

/**
 * This is the main application class of your custom application "myapp"
 *
 * @asset(webmln/*)
 */
qx.Class.define("webmln.Application",
{
//	extend : qx.application.Standalone,
	extend : qx.application.Inline,



  /*
  *****************************************************************************
     MEMBERS
  *****************************************************************************
  */

  	members :
  	{




        /**
         * This method contains the initial application code and gets called
         * during startup of the application
         *
         * @lint ignoreDeprecated(alert)
         */
        main : function() {
            // Call super class
            this.base(arguments);

              // Enable logging in debug variant
            if (qx.core.Environment.get("qx.debug")) {
                // support native logging capabilities, e.g. Firebug for Firefox
                qx.log.appender.Native;
                // support additional cross-browser console. Press F7 to toggle visibility
                qx.log.appender.Console;
            }

              /*
              -------------------------------------------------------------------------
            Below is your actual application code...
              -------------------------------------------------------------------------
              */

            var mln_container = document.getElementById("mln_container", true, true);
            var contentIsle = new qx.ui.root.Inline(mln_container,true,true);
            contentIsle.setWidth(document.getElementById("container", true, true).offsetWidth);
            contentIsle.setHeight(document.getElementById("container", true, true).offsetHeight);
            contentIsle.setLayout(new qx.ui.layout.Grow());

            mln_container.addEventListener("resize", function() {
                var w = document.getElementById("container", true, true).offsetWidth;
                var h = document.getElementById("container", true, true).offsetHeight;
                contentIsle.setWidth(w);
                contentIsle.setHeight(h);
            }, this);

            document.addEventListener("roll", function(e) {
                this[0].scrollTop = this[0].scrollTop + e.delta.y;
                this[0].scrollLeft = this[0].scrollLeft + e.delta.x;
            }, this);

            window.addEventListener("resize", function() {
                var w = document.getElementById("container", true, true).offsetWidth;
                var h = document.getElementById("container", true, true).offsetHeight;
                contentIsle.setWidth(w);
                contentIsle.setHeight(h);
            }, this);

            var response = null;
            var req = null;
            var layout = new qx.ui.layout.HBox();
            var layout3 = new qx.ui.layout.Grow();
            var layout4 = new qx.ui.layout.Grow();
            //layout2.setRowFlex(4, 1);
            //layout2.setRowFlex(12, 1);

            var textAreaResults = new qx.ui.form.TextArea("");
            this.__textAreaResults = textAreaResults;
            textAreaResults.setReadOnly(true);

            var outerContainer = new qx.ui.container.Scroll().set({
                //width: isNaN(window.innerWidth) ? window.clientWidth : window.innerWidth,
                //height: isNaN(window.innerHeight) ? window.clientHeight : window.innerHeight
            });

            var mlnFormContainer = this.buildMLNForm();

            var container = new qx.ui.container.Composite(new qx.ui.layout.VBox()).set({
                padding: 5
            });

            var splitPane = new qx.ui.splitpane.Pane("horizontal");
            var innerSplitPane = new qx.ui.splitpane.Pane("vertical");
            var innerMostSplitPane = new qx.ui.splitpane.Pane("vertical");
            var graphVizContainer = new qx.ui.container.Composite(new qx.ui.layout.Grow()).set({
                minHeight: 500, minWidth: 1200
            });

            var diaContainer = new qx.ui.container.Composite(new qx.ui.layout.Grow()).set({
                minHeight: 200, minWidth: 1200
            });
            splitPane.add(mlnFormContainer);

            var canvas = new qx.ui.container.Composite(new qx.ui.layout.Grow()).set({
                width: 1200, height: 500
            });
            var html = new qx.ui.embed.Html("<div id='dia' style='width: 100%; height: 100%;'></div>");
            //canvas.add(html);
            //var canvas = new qx.ui.groupbox.GroupBox("Visualization");
            //var vizLayout = new qx.ui.layout.Grow();
            //canvas.setLayout(vizLayout);
            var diaEmbedGrp = new qx.ui.groupbox.GroupBox("bla");
            var diaLayout = new qx.ui.layout.Grow();
            diaEmbedGrp.setLayout(diaLayout);
            diaEmbedGrp.add(html);
            //var html = new qx.ui.embed.Html('<div id="viz" style="width: 100%; height: 100%;"></div>');
            var vizEmbedGrp = new qx.ui.groupbox.GroupBox("Visualization");
            var vizLayout = new qx.ui.layout.Grow();
            vizEmbedGrp.setLayout(vizLayout);
            var vizHTML = "<div id='viz' style='width: 100%; height: 100%;'></div>";
            var vizEmbed = new qx.ui.embed.Html(vizHTML);
            vizEmbedGrp.add(vizEmbed);
            graphVizContainer.add(vizEmbedGrp);
            diaContainer.add(diaEmbedGrp);
            innerMostSplitPane.add(diaContainer);
            innerMostSplitPane.add(textAreaResults);
            innerSplitPane.add(graphVizContainer);
            innerSplitPane.add(innerMostSplitPane);

            splitPane.add(innerSplitPane);
            container.add(splitPane);
            outerContainer.add(splitPane);
            contentIsle.add(outerContainer, {width: "100%", height: "100%"});

            /*
            html.addListener("appear", function(e) {
                var div = d3.select('#d3');
                    var graph = div.append('svg:svg').attr('width', 400).attr('height', 400);

                    var pathinfo = [{x:0, y:60},
                                    {x:50, y:110},
                                    {x:90, y:70},
                                    {x:140, y:100}];

                    var line = d3.svg.line()
                                .x(function(d){return d.x;})
                                .y(function(d){return d.y;})
                                .interpolate('linear');

                    graph.append('svg:path').attr('d', line(pathinfo))
                            .style('stroke-width', 2)
                            .style('stroke', 'steelblue')
                            .style('fill', 'none');
            });*/

                //d3.json("resource/miserables1.json", function(error, graph) {
                  /*
                  var nody = new Object();
                  nody.name = "Ford";
                  nody.group = 1;
                  var nody2 = new Object();
                  nody2.name = "Opel";
                  nody2.group = 1;
                  var linky = new Object();
                  linky.source = 0;
                  linky.target = 1;
                  linky.value = 1;
                  var nodelist = [nody,nody2];
                  var linklist = [linky];
                  */

            var svg;
            var color;
            var force;
            var node;
            var link;
            var text;
            var textLabels;
            var prob;
            var probLabels;
            var nodeList = [];
            var linkList = [];

            function diaInit() {
                var width = 800, height = 100;
                color = d3.scale.category20();
                /*
                force = d3.layout.force()
                    .charge(-1000)
                    .linkDistance(200)
                    .size([width, height]);*/

                svg = d3.select('#dia').append("svg")
                    .attr("width", width)
                    .attr("height", height);

                //var linkList = [];
                var nody = new Object();
                //var linky;
                nody.id = 0;
                nody.name = 'Smokes, Cancer';
                nody.group = 1;
                nodeList.push(nody);
                for (var i = 0; i < resultStrings.length; i++) {
                    nody = new Object();
                    nody.id = i+1;
                    nody.name = resultStrings[i];
                    nody.group = 2;
                    /*
                    linky = new Object();
                    linky.prob = resultProb[i];
                    linky.source = nodeList[0];
                    linky.target = nody;*/
                    nodeList.push(nody);
                    //linkList.push(linky);

                }
                /*
                force
                    .nodes(nodeList)
                    .links(linkList)
                    .on("tick", tick);*/

                node = svg.selectAll(".node"),
                //link = svg.selectAll(".link");
                text = svg.selectAll(".nodeLabel");
                //prob = svg.selectAll(".edgeLabel");

                //d3Update();
                /*
                link = svg.selectAll(".link")
                    .data(linkList)
                    .enter().append("line")
                    .attr("class", "link")
                    .style("stroke-width", function(d) { return Math.sqrt(d.value); });*/

                node = svg.selectAll(".node")
                    .data(nodeList)
                    .enter().append("rect")
                    .attr("class", "node")
                    .attr("width", 100)
                    .attr("height", 50)
                    .attr("rx", 5)
                    .attr("ry", 5)
                    .style("fill", function(d) { return color(d.group); })
                    //.call(force.drag);

                node.append("title")
                    .text(function(d) { return d.name; });

                text = svg.selectAll("text")
                     .data(nodeList)
                     .enter().append("text")
                     .text(function(d) { return d.name; });

                textLabels = text
                     .attr("x", function(d) { return d.cx; })
                     .attr("y", function(d) { return d.cy; })
                     .attr("font-size", "20px")
                     .style("text-anchor", "middle")
                     .text(function(d) { return d.name; });
                /*
                force.on("tick", function() {
                     link.attr("x1", function(d) { return d.source.x; })
                         .attr("y1", function(d) { return d.source.y; })
                         .attr("x2", function(d) { return d.target.x; })
                         .attr("y2", function(d) { return d.target.y; });

                     node.attr("x", function(d) { return d.x-50; })
                         .attr("y", function(d) { return d.y-25; });

                     text.attr("x", function(d) { return d.x; })
                         .attr("y", function(d) { return d.y; });
                });*/
            }/*
            function d3Update() {
                for (var i = 0; i < nodeList.length; i++) {
                    nodeList[i].group = i;
                }
                if (!bogel) {
                    var nody = new Object();
                    nody.id = "5";
                    nody.name = "Fisch";
                    nody.group = 2;
                    nodeList.push(nody);
                    var linky = new Object();
                    linky.prob = 0.5;
                    linky.source = nodeList[1];
                    linky.target = nody;
                    linkList.push({prob: 0.5, source: 2, target: 5});
                }

                link = link.data(force.links(), function(d) { return d.source.id + "-" + d.target.id; });
                        link.enter().insert("line", ".node").attr("class", "link")
                            .style("stroke-width", function(d) { return Math.sqrt(d.value); });
                        link.exit().remove();

                node = node.data(force.nodes(), function(d) { return d.id;});
                        node.enter().append("rect").attr("class", function(d) { return "node " + d.id; })
                            .attr("width", 100)
                            .attr("height", 50)
                            .attr("rx", 5)
                            .attr("ry", 5)
                            .style("fill", function(d) { return color(d.group); })
                            .call(force.drag);
                        node.exit().remove();

                text = text.data(force.nodes(), function(d) { return d.id;});
                        text.enter().append("text").attr("class", "nodeLabel").text(function(d) { return d.name; });
                        text.exit().remove();

                textLabels = text
                     .attr("x", function(d) { return d.x; })
                     .attr("y", function(d) { return d.y; })
                     .attr("font-size", "20px")
                     .style("text-anchor", "middle");
        //	         .text(function(d) { return d.name; });

                prob = prob.data(force.links(), function(d) { return d.source.id + "-" + d.target.id; });
                        prob.enter().append("text").attr("class", "edgeLabel").text(function(d) { return d.prob; });
                        prob.exit().remove();

                probLabels = prob
                     .attr("x", function(d) { return 20; })
                     .attr("y", function(d) { return 20; })
                     .attr("font-size", "20px")
                     .style("text-anchor", "middle");
        //	         .text(function(d) { return d.prob; });
    /*
                text = svg.selectAll("text")
                     .data(nodeList)
                     .enter().append("text")
                     .text(function(d) { return d.name; });

                textLabels = text
                     .attr("x", function(d) { return d.cx; })
                     .attr("y", function(d) { return d.cy; })
                     .attr("font-size", "20px")
                     .style("text-anchor", "middle")
                     .text(function(d) { return d.name; });*/
    /*
                force.start();
                /*
                force
                    .nodes(nodeList)
                    .links(linkList)
                    .start();

                link = link.selectAll("line")
                    .data(linkList)
                    .enter().append("line")
                    .attr("class", "link")
                    .style("stroke-width", function(d) { return Math.sqrt(d.value); });

                //svg.selectAll(".node").data([]).exit().remove()

                node = node.selectAll("rect")
                    .data(nodeList)
                    .enter().append("rect")
                    .attr("class", "node")
                    .attr("width", 100)
                    .attr("height", 50)
                    .attr("rx", 5)
                    .attr("ry", 5)
                    .style("fill", function(d) { return color(d.group); })
                    .call(force.drag);*/

                /*
                node.append("title")
                    .text(function(d) { return d.name; });

                text = svg.selectAll("text")
                     .data(nodeList)
                     .enter().append("text")
                     .text(function(d) { return d.name; });

                textLabels = text
                     .attr("x", function(d) { return d.cx; })
                     .attr("y", function(d) { return d.cy; })
                     .attr("font-size", "20px")
                     .style("text-anchor", "middle")
                     .text(function(d) { return d.name; });*/
                /*
                force.on("tick", function() {
                     link.attr("x1", function(d) { return d.source.x; })
                         .attr("y1", function(d) { return d.source.y; })
                         .attr("x2", function(d) { return d.target.x; })
                         .attr("y2", function(d) { return d.target.y; });

                     node.attr("x", function(d) { return d.x-50; })
                         .attr("y", function(d) { return d.y-25; });

                     text.attr("x", function(d) { return d.x; })
                         .attr("y", function(d) { return d.y; });
                });*/
     /*       }
            function tick() {
                    link.attr("x1", function(d) { return d.source.x; })
                         .attr("y1", function(d) { return d.source.y; })
                         .attr("x2", function(d) { return d.target.x; })
                         .attr("y2", function(d) { return d.target.y; });

                     node.attr("x", function(d) { return d.x-50; })
                         .attr("y", function(d) { return d.y-25; });

                     text.attr("x", function(d) { return d.x; })
                         .attr("y", function(d) { return d.y; });

                     prob.attr("x", function(d) { return d.x; })
                         .attr("y", function(d) { return d.y; });
            }*/
            //graphVizContainer.add(canvas);

        },

        buildMLNForm : function() {

        var check = false;

        var mlnFormContainerLayout = new qx.ui.layout.Grid();
        mlnFormContainerLayout.setRowHeight(4, 200);
        mlnFormContainerLayout.setRowHeight(12, 100);

        var mlnFormContainer = new qx.ui.container.Composite(mlnFormContainerLayout).set({
                padding: 10
            });

        var engineLabel = new qx.ui.basic.Label("Engine:");
            var grammarLabel = new qx.ui.basic.Label("Grammar:");
            var logicLabel = new qx.ui.basic.Label("Logic:");
            var mlnLabel = new qx.ui.basic.Label("MLN:");
            var evidenceLabel = new qx.ui.basic.Label("Evidence:");
            var methodLabel = new qx.ui.basic.Label("Method:");
            var queriesLabel = new qx.ui.basic.Label("Queries:");
            var maxStepsLabel = new qx.ui.basic.Label("Max. steps:");
            var numChainsLabel = new qx.ui.basic.Label("Num. chains:");
            var addParamsLabel = new qx.ui.basic.Label("Add. params:");
            var cwPredsLabel = new qx.ui.basic.Label("CW preds:");
            var outputLabel = new qx.ui.basic.Label("Output:");

            var buttonStart = new qx.ui.form.Button(">>Start Inference<<", null);
            var buttonSaveMLN = new qx.ui.form.Button("save", null);
            var buttonSaveEvidence = new qx.ui.form.Button("save", null);
            var buttonSaveEMLN = new qx.ui.form.Button("save",null);

            var selectEngine = new qx.ui.form.SelectBox();
            var selectGrammar = new qx.ui.form.SelectBox();
            var selectLogic = new qx.ui.form.SelectBox();
            var selectMLN = new qx.ui.form.SelectBox();
            var selectEMLN = new qx.ui.form.SelectBox();
            var selectEvidence = new qx.ui.form.SelectBox();
            var selectMethod = new qx.ui.form.SelectBox();

            var textAreaMLN = new qx.ui.form.TextArea("");
            var textAreaEMLN = new qx.ui.form.TextArea("");
            var textAreaEvidence = new qx.ui.form.TextArea("");


            var textFieldNameMLN = new qx.ui.form.TextField("");
            textFieldNameMLN.setEnabled(false);
            var textFieldNameEMLN = new qx.ui.form.TextField("");
            var textFieldCWPreds = new qx.ui.form.TextField("");
            var textFieldOutput = new qx.ui.form.TextField("");
            var textFieldDB = new qx.ui.form.TextField("");
            var textFieldQueries = new qx.ui.form.TextField("");
            var textFieldMaxSteps = new qx.ui.form.TextField("");
            var textFieldNumChains = new qx.ui.form.TextField("");
            var textFieldAddParams = new qx.ui.form.TextField("");

            var checkBoxRenameEditMLN = new qx.ui.form.CheckBox("rename on edit");
            var checkBoxRenameEditEvidence = new qx.ui.form.CheckBox("rename on edit");
            var checkBoxRenameEditEMLN = new qx.ui.form.CheckBox("rename on edit");
            var checkBoxConvertAlchemy = new qx.ui.form.CheckBox("convert to Alchemy format");
            var checkBoxUseModelExt = new qx.ui.form.CheckBox("use model extension");
            var checkBoxApplyCWOption = new qx.ui.form.CheckBox("Apply CW assumption to all but the query preds");
            var checkBoxUseAllCPU = new qx.ui.form.CheckBox("Use all CPUs");
            var checkBoxSaveOutput = new qx.ui.form.CheckBox("save");

            textFieldOutput.setValue("smoking-test-smoking.results");
            buttonStart.addListener("execute",function(e) {
                                var that = this;

                                //req = new qx.io.remote.Request("/_start_inference", "GET", "text/plain");
                                req = new qx.io.request.Xhr
                                ("/mln/_start_inference","GET");
                                var mln = (selectMLN.getSelectables().length != 0) ? selectMLN.getSelection()[0].getLabel() : "";
                                var emln = (selectEMLN.getSelectables().length != 0) ? selectEMLN.getSelection()[0].getLabel() : "";
                                var db = (selectEvidence.getSelectables().length != 0) ? selectEvidence.getSelection()[0].getLabel() : "";
                                var method = (selectMethod.getSelectables().length != 0) ? selectMethod.getSelection()[0].getLabel() : "";
                                var engine = (selectEngine.getSelectables().length != 0) ? selectEngine.getSelection()[0].getLabel() : "";
                                var logic = (selectLogic.getSelectables().length != 0) ? selectLogic.getSelection()[0].getLabel() : "";
                                var grammar = (selectGrammar.getSelectables().length != 0) ? selectGrammar.getSelection()[0].getLabel() : "";
                                req.setRequestData({"mln":mln,"emln":emln,"db":db,"method":method,"engine":engine,"logic":logic,"grammar":grammar,"mln_text":textAreaMLN.getValue                       (),"db_text":textAreaEvidence.getValue(),"output":textFieldOutput.getValue(),"params":textFieldAddParams.getValue(),"mln_rename_on_edit":checkBoxRenameEditMLN.getValue(),"db_rename_on_edit":checkBoxRenameEditEvidence.getValue(),"query":textFieldQueries.getValue(),"closed_world":checkBoxApplyCWOption.getValue(),"cw_preds":textFieldCWPreds.getValue(),"convert_to_alchemy":checkBoxConvertAlchemy.getValue(),"use_emln":checkBoxUseModelExt.getValue(),"max_steps":textFieldMaxSteps.getValue(),"num_chains":textFieldNumChains.getValue(),"use_multicpu":checkBoxUseAllCPU.getValue()});
                                req.addListener("success", function(e) {
                                        var tar = e.getTarget();
                                        //response = e.getContent();
                                        response = tar.getResponse();
                                        console.log('response', response);

                                        var atoms = response.atoms;
                                        var formulas = response.formulas;
                                        var keys = response.resultkeys;
                                        var values = response.resultvalues;
                                        var resultsMap = new Object();
                                        for (var i = 0; i < keys.length; i++) {
                                                resultsMap[keys[i]] = values[i];
                                        }
                                        var output = response.output;
                                        var formulaAtoms = [];
                                        for (var i = 0; i < formulas.length; i++) {
                                            formulaAtoms[i] = [];
                                            for (var j = 0; j < atoms.length; j++) {
                                                if (formulas[i].indexOf(atoms[j]) > -1 && (formulaAtoms[i].indexOf(atoms[j]) == -1)) {
                                                    formulaAtoms[i].push(atoms[j]);
                                                }
                                            }
                                        }
                                        var duplicates = [];
                                        var splitAtoms = [];
                                        for (var i = 0; i < atoms.length; i++) {
                                            splitAtoms[i] = [];
                                            splitAtoms[i][0] = atoms[i].split("(")[0];
                                            splitAtoms[i][1] = atoms[i].slice(atoms[i].indexOf("(")+1,atoms[i].indexOf(")")).split(",").sort();
                                        }
                                        for (var i = 0; i < splitAtoms.length; i++) {
                                            var skip = false;
                                            for (var j = 0; j < splitAtoms[i][1].length; j++) {
                                                for (var k = 0; k < splitAtoms[i][1].length; k++) {
                                                    if (j >= k) continue;
                                                    if (splitAtoms[i][1][j] == splitAtoms[i][1][k]) {
                                                        duplicates.push(atoms[i]);
                                                        skip = true;
                                                        break;
                                                    }
                                                }
                                                if (skip) break;
                                            }
                                            for (var j = 0; j < splitAtoms.length; j++) {
                                                if (i >= j) continue;

                                                if (splitAtoms[i][0] == splitAtoms[j][0] && splitAtoms[i][1].join(",") == splitAtoms[j][1].join(",")) {
                                                    duplicates.push(atoms[i]);
                                                }
                                            }
                                        }
                                        var hasDuplicates = []
                                        for (var i = 0; i < formulaAtoms.length; i++) {
                                            hasDuplicates[i] = false;
                                            for (var j = 0; j < duplicates.length; j++) {
                                                 if (formulaAtoms[i].indexOf(duplicates[j]) > -1) {
                                                      hasDuplicates[i] = true;
                                                      break;
                                                 }
                                            }
                                        }

                                        that.loadGraph();
                                        var addList = [];
                                        var checkList;
                                        var link;

                                        for (var i = 0; i < formulaAtoms.length; i++) {
                                            if (hasDuplicates[i]) continue;
                                            checkList = [];
                                            for (var j = 0; j < formulaAtoms[i].length; j++) {
                                                checkList[j] = [];
                                                for (var k = 0; k < formulaAtoms[i].length; k++) {
                                                    if (j != k) {
                                                        if (j > k && checkList[k].indexOf(j) > -1) {
                                                            continue;
                                                        }
                                                        checkList[j].push(k);
                                                        link = new Object();
                                                        link.source = formulaAtoms[i][j];
                                                        link.target = formulaAtoms[i][k];
                                                        link.value = formulas[i];
                                                        link.arcStyle = "strokegreen";
                                                        addList.push(link);
                                                    }
                                                }
                                            }
                                        }
                                        that.updateGraph([],addList);
                                        if (check) {
                                            that.updateBarChart(resultsMap);
                                        } else {
                                            check = true;
                                            that.d3BarChart(resultsMap);
                                        }
                                        //that.updateGraph([],addList);
                                        //labelResults.setValue(response);

                                        that.__textAreaResults.setValue
                                        (output);
                                        that.__textAreaResults
                                        .getContentElement().scrollToY(10000);

                                });
                                req.send();

            }, this);
            buttonSaveMLN.addListener("execute",function(e){
                                //req = new qx.io.remote.Request("/mln/_test",
    //						    "GET", "text/plain");
                                //req.addListener("completed", function(e) {
                                //		alert(e.getContent());
                                //});
                                //req.send();

            });
            buttonSaveEMLN.addListener("execute",function(e){});
            buttonSaveEvidence.addListener("execute",function(e){});

            checkBoxRenameEditMLN.addListener("changeValue",function(e){});
            checkBoxRenameEditEvidence.addListener("changeValue",function(e){});
            checkBoxRenameEditEMLN.addListener("changeValue",function(e){});
            checkBoxConvertAlchemy.addListener("changeValue",function(e){});
            checkBoxUseModelExt.addListener("changeValue",function(e) {
                                        if (Boolean(checkBoxUseModelExt.getValue())) {
                                            mlnFormContainer.add(selectEMLN, {row: 7, column: 1, colSpan: 2});
                                            mlnFormContainer.add(buttonSaveEMLN, {row: 7, column: 3});
                                            mlnFormContainer.add(textAreaEMLN, {row: 8, column: 1, colSpan: 3});
                                            mlnFormContainer.add(checkBoxRenameEditEMLN, {row: 9, column: 1});
                                            mlnFormContainer.add(textFieldNameEMLN, {row: 10, column: 1, colSpan: 3});
                                            layout.setRowFlex(8, 1);
                                            req = new qx.io.request.Xhr
                                            ("/mln/_use_model_ext", "GET");
                                            req.addListener("success", function(e) {
                                                var tar = e.getTarget();
                                                response = tar.getResponse().split(",");
                                                //response = e.getContent().split(",");
                                                for (var i = 0; i < response.length; i++) {
                                                    selectEMLN.add(new qx.ui.form.ListItem(response[i]));
                                                }
                                            });
                                            req.send();
                                        } else {
                                            mlnFormContainer.remove(selectEMLN);
                                            mlnFormContainer.remove(buttonSaveEMLN);
                                            mlnFormContainer.remove(textAreaEMLN);
                                            mlnFormContainer.remove(checkBoxRenameEditEMLN);
                                            mlnFormContainer.remove(textFieldNameEMLN);
                                            layout.setRowFlex(8, 0);
                                            selectEMLN.removeAll();
                                            textAreaEMLN.setValue("");
                                            checkBoxRenameEditEMLN.setValue(Boolean(false));
                                            textFieldNameEMLN.setValue("");
                                        }
                                    });
            checkBoxApplyCWOption.addListener("changeValue",function(e){});
            checkBoxUseAllCPU.addListener("changeValue",function(e){});
            checkBoxSaveOutput.addListener("changeValue",function(e){});
            selectEngine.addListener("changeSelection",function(e) {
                                        var item = selectEngine.getSelection()[0];
                                        req = new qx.io.request.Xhr
                                        ("/mln/_change_engine", "GET");
                                        req.setRequestData({"engine":item.getLabel()});
                                        //req.setParameter("engine", item.getLabel());
                                        req.addListener("success", function(e) {
                                            var tar = e.getTarget();
                                            response = tar.getResponse().split(";");
                                            //response = e.getContent().split(";");
                                            var params = response[0];
                                            var methods = response[2].split(",");
                                            if (item.getLabel() == "J-MLNs") {
                                                checkBoxApplyCWOption.setEnabled(false);
                                            } else {
                                                checkBoxApplyCWOption.setEnabled(true);
                                            }
                                            selectMethod.removeAll();
                                            for (var i = 0; i < methods.length; i++) {
                                                selectMethod.add(new qx.ui.form.ListItem(methods[i]));
                                            }
                                            for (var i = 0; i < selectMethod.getSelectables().length; i++) {
                                                if (selectMethod.getSelectables()[i].getLabel() == response[1]) {
                                                    selectMethod.setSelection([selectMethod.getSelectables()[i]]);
                                                }
                                            }
                                            textFieldAddParams.setValue(params);
                                        });
                                        req.send();

            });
            selectGrammar.addListener("changeSelection",function(e){});
            selectLogic.addListener("changeSelection",function(e){});
            selectMLN.addListener("changeSelection",function(e){
                                        var item = selectMLN.getSelection()[0];
                                        textFieldNameMLN.setValue(item.getLabel());
                                        req = new qx.io.request.Xhr("/mln/_mln",
                                        "GET");
                                        req.setRequestData({"filename":item.getLabel()});
                                        //req.setParameter("filename", item.getLabel());
                                        req.addListener("success", function(e) {
                                            var tar = e.getTarget();
                                            //response = e.getContent();
                                            response = tar.getResponse();
                                            textAreaMLN.setValue(response);

                                        });
                                        req.send();


            });
            selectEMLN.addListener("changeSelection",function(e){});
            selectEvidence.addListener("changeSelection",function(e){
                                        var item = selectEvidence.getSelection()[0];
                                        textFieldDB.setValue(item.getLabel());
                                        req = new qx.io.request.Xhr("/mln/_load_evidence", "GET");
                                        req.setRequestData({"filename":item.getLabel()});
                                        req.addListener("success", function(e) {
                                            var tar = e.getTarget();
                                            var response = tar.getResponse();
                                            textAreaEvidence.setValue(response.text);
                                            textFieldQueries.setValue(response.query);
                                        });
                                        req.send();
            });
            selectMethod.addListener("changeSelection",function(e){});
            selectEngine.add(new qx.ui.form.ListItem("PRACMLNs"));
            selectEngine.add(new qx.ui.form.ListItem("J-MLNs"));
            selectGrammar.add(new qx.ui.form.ListItem("StandardGrammar"));
            selectGrammar.add(new qx.ui.form.ListItem("PRACGrammar"));
            selectLogic.add(new qx.ui.form.ListItem("FirstOrderLogic"));
            selectLogic.add(new qx.ui.form.ListItem("FuzzyLogic"));
            mlnFormContainer.add(engineLabel, {row: 0, column: 0});
            mlnFormContainer.add(grammarLabel, {row: 1, column: 0});
            mlnFormContainer.add(logicLabel, {row: 2, column: 0});
            mlnFormContainer.add(mlnLabel, {row: 3, column: 0});
            mlnFormContainer.add(evidenceLabel, {row: 11, column: 0});
            mlnFormContainer.add(methodLabel, {row: 15, column: 0});
            mlnFormContainer.add(queriesLabel, {row: 16, column: 0});
            mlnFormContainer.add(maxStepsLabel, {row: 17, column: 0});
            mlnFormContainer.add(numChainsLabel, {row: 18, column: 0});
            mlnFormContainer.add(addParamsLabel, {row: 19, column: 0});
            mlnFormContainer.add(cwPredsLabel, {row: 20, column: 0});
            mlnFormContainer.add(outputLabel, {row: 21, column: 0});
            mlnFormContainer.add(selectEngine, {row: 0, column: 1, colSpan: 3});
            mlnFormContainer.add(selectGrammar, {row: 1, column: 1, colSpan: 3});
            mlnFormContainer.add(selectLogic, {row: 2, column: 1, colSpan: 3});
            mlnFormContainer.add(selectMLN, {row: 3, column: 1, colSpan: 2});
            mlnFormContainer.add(selectEvidence, {row: 11, column: 1, colSpan: 2});
            mlnFormContainer.add(selectMethod, {row: 15, column: 1, colSpan: 3});

            mlnFormContainer.add(buttonStart, {row: 22, column: 1, colSpan: 3});
            mlnFormContainer.add(buttonSaveMLN, {row: 3, column: 3});
            mlnFormContainer.add(buttonSaveEvidence, {row: 11, column: 3});

            mlnFormContainer.add(textAreaMLN, {row: 4, column: 1, colSpan: 3});
            mlnFormContainer.add(textAreaEvidence, {row: 12, column: 1, colSpan: 3});
            mlnFormContainer.add(textFieldNameMLN, {row: 6, column: 1, colSpan: 3});
            mlnFormContainer.add(textFieldDB, {row: 14, column: 1, colSpan: 3});
            mlnFormContainer.add(textFieldQueries, {row: 16, column: 1, colSpan: 3});
            mlnFormContainer.add(textFieldMaxSteps, {row: 17, column: 1, colSpan: 3});
            mlnFormContainer.add(textFieldNumChains, {row: 18, column: 1, colSpan: 3});
            mlnFormContainer.add(textFieldAddParams, {row: 19, column: 1, colSpan: 3});
            mlnFormContainer.add(textFieldCWPreds, {row: 20, column: 1});
            mlnFormContainer.add(textFieldOutput, {row: 21, column: 1, colSpan: 2});

            mlnFormContainer.add(checkBoxRenameEditMLN, {row: 5, column: 1});
            mlnFormContainer.add(checkBoxConvertAlchemy, {row: 5, column: 2});
            mlnFormContainer.add(checkBoxUseModelExt, {row: 5, column: 3});
            mlnFormContainer.add(checkBoxRenameEditEvidence, {row: 13, column: 1});
            mlnFormContainer.add(checkBoxApplyCWOption, {row: 20, column: 2});
            mlnFormContainer.add(checkBoxUseAllCPU, {row: 20, column: 3});
            mlnFormContainer.add(checkBoxSaveOutput, {row: 21, column: 3});


            //Fetch options to choose from
            req = new qx.io.request.Xhr("/mln/_init", "GET");
            req.addListener("success", function(e) {
                                var tar = e.getTarget();
                                var response = tar.getResponse();
                                var sub;
                                textFieldQueries.setValue(response.queries);
                                textFieldMaxSteps.setValue(response.maxSteps);

                                var arr = ['files', 'engines','infMethods', 'dbs'];
                                for (var x = 0; x < arr.length; x++) {
                                    for (var i = 0; i < response[arr[x]].length; i++) {
                                        (arr[x] == 'files' ? selectMLN : arr[x] ==
                                         'engines' ? selectEngine : arr[x] ==
                                         'infMethods' ? selectMethod :
                                         selectEvidence).add(new qx.ui.form.ListItem(response[arr[x]][i]));
                                    }
                                }
            });
            req.send();

            return mlnFormContainer;
        },

        updateGraph : function(removeLinks, addLinks) {
          this._graph.updateData(removeLinks, addLinks);
        },

        loadGraph : function() {
          if (typeof this._graph === 'undefined') {
            this._graph = new webmln.Graph();
          }
          this._graph.clear();
        },

        _calculateRedrawing : function(oldRes, newRes) {
          var toBeRemoved = [];
          var toBeAdded = [];
          var remove;
          var add;

          // old links to be removed
          for (var i = 0; i < oldRes.length; i++) {
            remove = true;
            for (var j = 0; j < newRes.length; j++) {
              // if there is already a link between the nodes, do not remove it
              if (oldRes[i].source === newRes[j].source && oldRes[i].target === newRes[j].target && oldRes[i].value === newRes[j].value) {
                remove = false;
                break;
              }
            }
            if (remove) {
              toBeRemoved.push(oldRes[i]);
            }
          }

          // new links to be added
          for (var i = 0; i < newRes.length; i++) {
            add = true;
            for (var j = 0; j < oldRes.length; j++) {
              // if there is already a link, do not add it
              if (newRes[i].target === oldRes[j].target && newRes[i].source === oldRes[j].source && newRes[i].value === oldRes[j].value) {
                add = false;
                break;
              }
            }
            if (add) {
              toBeAdded.push(newRes[i]);
            }
          }

          return [toBeRemoved, toBeAdded];
        },


        d3BarChart : function(results) {
            console.log('results', results);
            var bar;
            var xAxis;
            var yAxis;
            var x;
            var y;
            var format;
            var data = [];

            var m = [30, 10, 10, 250],
            w = 960 - m[1] - m[3],
            h = 130 - m[0] - m[2];

            format = d3.format(".4f");

            x = d3.scale.linear().range([0, w]),
            y = d3.scale.ordinal().rangeRoundBands([0, h], .1);

            xAxis = d3.svg.axis().scale(x).orient("top").tickSize(-h);
            yAxis = d3.svg.axis().scale(y).orient("left").tickSize(0);

            svg = d3.select("#dia").append("svg")
              .attr("width", w + m[1] + m[3])
              .attr("height", h + m[0] + m[2])
              .append("g")
              .attr("transform", "translate(" + m[3] + "," + m[0] + ")");

            for (var key in results) {
                if (results.hasOwnProperty(key)) {
                    var data1 = new Object();
                    data1.name = key;
                    data1.value = results[key];
                    data.push(data1);
                }
            }
            // Parse numbers, and sort by value.
            //data.forEach(function(d) { d.value = +d.value; });
            data.sort(function(a, b) { return b.value - a.value; });

            // Set the scale domain.
            //x.domain([0, d3.max(data, function(d) { return d.value; })]);
            x.domain([0,1]);
            y.domain(data.map(function(d) { return d.name; }));

            bar = svg.selectAll("g.bar")
                .data(data,function(d) {
                console.log('data', data);
                return d.name; })
                .enter().append("g")
                .attr("class", "bar")
                .attr("transform", function(d) { return "translate(0," + y(d.name) + ")"; });

            bar.append("rect")
                .attr("width", function(d) { return x(d.value); })
                .attr("height", y.rangeBand());

            bar.append("text")
                .attr("class", "value")
                .attr("x", function(d) { return x(d.value); })
                .attr("y", y.rangeBand() / 2)
                .attr("dx", -3)
                .attr("dy", ".35em")
                .attr("text-anchor", "end")
                .text(function(d) { return format(d.value); });

            svg.append("g")
                .attr("class", "x axis")
                .call(xAxis);

            svg.append("g")
                .attr("class", "y axis")
                .call(yAxis);
        },


        updateBarChart : function(results) {

                data = [];
                var data1 = new Object();
                data1.name = "Franz";
                data1.value = 0.15;
                data.push(data1);
                data1 = new Object();
                data1.name = "Hans";
                data1.value = 0.9;
                data.push(data1);

                y.domain(data.map(function(d) { return d.name; }));

                bar = bar.data(data,function(d) { return d.name; });
                        bar.enter().append("rect")
                    .attr("width", function(d) { return x(d.value); })
                    .attr("height", y.rangeBand())
                    .attr("transform", function(d) { return "translate(0," + y(d.name) + ")"; });
                        bar.enter().append("text")
                    .attr("class", "value")
                    .attr("x", function(d) { return x(d.value); })
                    .attr("y", y.rangeBand() / 2)
                    .attr("dx", -3)
                    .attr("dy", ".35em")
                    .attr("text-anchor", "end")
                    .text(function(d) { return format(d.value); });
                        bar.exit().remove();

                    //svg.select("g").call(yAxis);
            }

    }   
});
