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
            this.__contentIsle = contentIsle;
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

            var outerContainer = new qx.ui.container.Scroll();
            var splitPane = this.getSplitPane();

            var tabView = new qx.ui.tabview.TabView();
            tabView.setWidth(500);

            ////////////////// INFERENCE PAGE ////////////////////
            var inferencePage = new qx.ui.tabview.Page("Inference");
            inferencePage.setLayout(new qx.ui.layout.Grow());
            inferencePage.add(splitPane);
            tabView.add(inferencePage);

            ////////////////// LEARNING PAGE ////////////////////
            var learningPage = new qx.ui.tabview.Page("Learning");
            learningPage.setLayout(new qx.ui.layout.VBox());
            learningPage.add(new qx.ui.basic.Label("Layout-Settings"));
            tabView.add(learningPage);

            outerContainer.add(tabView);
            contentIsle.add(outerContainer, {width: "100%", height: "100%"});
        },

        /**
        * Build the outer splitpane containing the mln form and vizualization containers
        */
        getSplitPane : function() {

            var textAreaResults = new qx.ui.form.TextArea("");
            this.__textAreaResults = textAreaResults;
            textAreaResults.setReadOnly(true);

            var mlnFormContainer = this.buildMLNForm();
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
            var diaEmbedGrp = new qx.ui.groupbox.GroupBox("Statistics");
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

            return splitPane;

        },

        /**
        * Build the query mln form
        */
        buildMLNForm : function() {

            this.check = false;
            var mlnFormContainerLayout = new qx.ui.layout.Grid();
            this.__mlnFormContainerLayout = mlnFormContainerLayout;
            mlnFormContainerLayout.setRowHeight(4, 200);
            mlnFormContainerLayout.setRowHeight(12, 100);
            var mlnFormContainer = new qx.ui.container.Composite(mlnFormContainerLayout).set({
                    padding: 10
            });
            this.__mlnFormContainer = mlnFormContainer;

            // labels
            var exampleFolderLabel = new qx.ui.basic.Label().set({
                value: this._template('Example:', 'label'),
                rich : true
            });
            var grammarLabel = new qx.ui.basic.Label().set({
                value: this._template('Grammar:', 'label'),
                rich : true
            });
            var logicLabel = new qx.ui.basic.Label().set({
                value: this._template('Logic:', 'label'),
                rich : true
            });
            var mlnLabel = new qx.ui.basic.Label().set({
                value: this._template('MLN:', 'label'),
                rich : true
            });
            this.__emlnLabel = new qx.ui.basic.Label().set({
                value: this._template('EMLN:', 'label'),
                rich : true
            });
            var evidenceLabel = new qx.ui.basic.Label().set({
                value: this._template('Evidence:', 'label'),
                rich : true
            });
            var methodLabel = new qx.ui.basic.Label().set({
                value: this._template('Method:', 'label'),
                rich : true
            });
            var queriesLabel = new qx.ui.basic.Label().set({
                value: this._template('Queries:', 'label'),
                rich : true
            });
            var verboseStepsLabel = new qx.ui.basic.Label().set({
                value: this._template('Verbose:', 'label'),
                rich : true
            });
            var addParamsLabel = new qx.ui.basic.Label().set({
                value: this._template('Params:', 'label'),
                rich : true
            });
            var cwPredsLabel = new qx.ui.basic.Label().set({
                value: this._template('CW Preds:', 'label'),
                rich : true
            });
            var outputLabel = new qx.ui.basic.Label().set({
                value: this._template('Output:', 'label'),
                rich : true
            });

            // widgets
            this.__selectExampleFolder = new qx.ui.form.SelectBox();
            this.__selectGrammar = new qx.ui.form.SelectBox();
            this.__selectLogic = new qx.ui.form.SelectBox();
            this.__selectMLN = new qx.ui.form.SelectBox();
            this.__folderButton = new com.zenesis.qx.upload.UploadButton("Load File");
            this.__uploader = new com.zenesis.qx.upload.UploadMgr(this.__folderButton, "/mln/mln_file_upload");
                this.__uploader.setAutoUpload(false);
            this.__textFieldNameMLN = new qx.ui.form.TextField("");
                this.__textFieldNameMLN.setEnabled(false);
            this.__buttonSaveMLN = new qx.ui.form.Button("save", null);
            this.__checkBoxRenameEditMLN = new qx.ui.form.CheckBox("rename on edit");

            var mlnAreaContainerLayout = new qx.ui.layout.Grow();
            this.__mlnAreaContainer = new qx.ui.container.Composite(mlnAreaContainerLayout);
            this.__textAreaMLN = new qx.ui.form.TextArea("");
            this.__textAreaMLN.getContentElement().setAttribute("id", 'mlnArea');
            this.__mlnAreaContainer.add(this.__textAreaMLN);

            this.__checkBoxUseModelExt = new qx.ui.form.CheckBox("use model extension");
            this.__selectEMLN = new qx.ui.form.SelectBox();
            this.__buttonSaveEMLN = new qx.ui.form.Button("save",null);
            this.__checkBoxRenameEditEMLN = new qx.ui.form.CheckBox("rename on edit");
            this.__textFieldNameEMLN = new qx.ui.form.TextField("");

            var emlnAreaContainerLayout = new qx.ui.layout.Grow();
            this.__emlnAreaContainer = new qx.ui.container.Composite(emlnAreaContainerLayout);
            this.__textAreaEMLN = new qx.ui.form.TextArea("");
            this.__textAreaEMLN.getContentElement().setAttribute("id", 'emlnArea');
            this.__emlnAreaContainer.add(this.__textAreaEMLN);

            this.__selectEvidence = new qx.ui.form.SelectBox();
            this.__buttonSaveEvidence = new qx.ui.form.Button("save", null);
            this.__checkBoxRenameEditEvidence = new qx.ui.form.CheckBox("rename on edit");
            this.__textFieldDB = new qx.ui.form.TextField("");

            var evidenceContainerLayout = new qx.ui.layout.Grow();
            this.__evidenceContainer = new qx.ui.container.Composite(evidenceContainerLayout);
            this.__textAreaEvidence = new qx.ui.form.TextArea("");
            this.__textAreaEvidence.getContentElement().setAttribute("id", 'dbArea');
            this.__evidenceContainer.add(this.__textAreaEvidence);

            this.__selectMethod = new qx.ui.form.SelectBox();
            this.__textFieldQueries = new qx.ui.form.TextField("");
            this.__textFieldVerbose = new qx.ui.form.TextField("");
            this.__textFieldCWPreds = new qx.ui.form.TextField("");
            this.__checkBoxApplyCWOption = new qx.ui.form.CheckBox("Apply CW assumption to all but the query preds");
            this.__textFieldAddParams = new qx.ui.form.TextField("");
            this.__textFieldOutput = new qx.ui.form.TextField("");
                this.__textFieldOutput.setValue("smoking-test-smoking.results");
            this.__checkBoxSaveOutput = new qx.ui.form.CheckBox("save");
            this.__checkBoxUseAllCPU = new qx.ui.form.CheckBox("Use all CPUs");
            this.__checkBoxIgnoreUnknown = new qx.ui.form.CheckBox("Ignore Unknown Predicates");
            this.__checkBoxShowLabels = new qx.ui.form.CheckBox("Show Formulas");
            this.__buttonStart = new qx.ui.form.Button("Start Inference", null);

            // add static listitems
            this.__selectGrammar.add(new qx.ui.form.ListItem("StandardGrammar"));
            this.__selectGrammar.add(new qx.ui.form.ListItem("PRACGrammar"));
            this.__selectLogic.add(new qx.ui.form.ListItem("FirstOrderLogic"));
            this.__selectLogic.add(new qx.ui.form.ListItem("FuzzyLogic"));

            // listeners
            this.__buttonStart.addListener("execute", this._start_inference, this);
            this.__checkBoxUseModelExt.addListener("changeValue", this._showModelExtension, this);
            this.__selectMLN.addListener("changeSelection", this._update_mln_text, this);
            this.__selectExampleFolder.addListener("changeSelection", this._change_example ,this);
            this.__selectEvidence.addListener("changeSelection", this._update_evidence_text, this);
            this.__uploader.addListener("addFile", this._upload, this);
            this.__textAreaEMLN.addListener("appear", this._update_emln_text, this);
            this.__checkBoxShowLabels.addListener("changeValue", function(e) {
                            this._graph.showLabels(e.getData());
                        }, this);

            // add widgets to form
            this.__mlnFormContainer.add(exampleFolderLabel, {row: 0, column: 0});
            this.__mlnFormContainer.add(grammarLabel, {row: 1, column: 0});
            this.__mlnFormContainer.add(logicLabel, {row: 2, column: 0});
            this.__mlnFormContainer.add(mlnLabel, {row: 3, column: 0});
            this.__mlnFormContainer.add(evidenceLabel, {row: 11, column: 0});
            this.__mlnFormContainer.add(methodLabel, {row: 15, column: 0});
            this.__mlnFormContainer.add(queriesLabel, {row: 16, column: 0});
            this.__mlnFormContainer.add(verboseStepsLabel, {row: 17, column: 0});
            this.__mlnFormContainer.add(addParamsLabel, {row: 19, column: 0});
            this.__mlnFormContainer.add(cwPredsLabel, {row: 20, column: 0});
            this.__mlnFormContainer.add(outputLabel, {row: 21, column: 0});

            this.__mlnFormContainer.add(this.__selectExampleFolder, {row: 0, column: 1, colSpan: 3});
            this.__mlnFormContainer.add(this.__selectGrammar, {row: 1, column: 1, colSpan: 3});
            this.__mlnFormContainer.add(this.__selectLogic, {row: 2, column: 1, colSpan: 3});
            this.__mlnFormContainer.add(this.__selectMLN, {row: 3, column: 1, colSpan: 2});
            this.__mlnFormContainer.add(this.__folderButton, {row: 3, column: 3});
            this.__mlnFormContainer.add(this.__mlnAreaContainer, {row: 4, column: 1, colSpan: 3});
//            this.__mlnFormContainer.add(this.__checkBoxRenameEditMLN, {row: 5, column: 1});
            this.__mlnFormContainer.add(this.__checkBoxUseModelExt, {row: 5, column: 1});
//            this.__mlnFormContainer.add(this.__textFieldNameMLN, {row: 6, column: 1, colSpan: 2});
//            this.__mlnFormContainer.add(this.__buttonSaveMLN, {row: 6, column: 3});

            this.__mlnFormContainer.add(this.__selectEvidence, {row: 11, column: 1, colSpan: 3});
//            this.__mlnFormContainer.add(this.__buttonSaveEvidence, {row: 11, column: 3});
            this.__mlnFormContainer.add(this.__evidenceContainer, {row: 12, column: 1, colSpan: 3});
//            this.__mlnFormContainer.add(this.__checkBoxRenameEditEvidence, {row: 13, column: 1});
//            this.__mlnFormContainer.add(this.__textFieldDB, {row: 14, column: 1, colSpan: 3});
            this.__mlnFormContainer.add(this.__selectMethod, {row: 15, column: 1, colSpan: 3});
            this.__mlnFormContainer.add(this.__textFieldQueries, {row: 16, column: 1, colSpan: 3});
            this.__mlnFormContainer.add(this.__textFieldVerbose, {row: 17, column: 1, colSpan: 3});
            this.__mlnFormContainer.add(this.__textFieldAddParams, {row: 19, column: 1, colSpan: 3});
            this.__mlnFormContainer.add(this.__textFieldCWPreds, {row: 20, column: 1, colSpan: 2});
            this.__mlnFormContainer.add(this.__checkBoxApplyCWOption, {row: 20, column: 3});
            this.__mlnFormContainer.add(this.__textFieldOutput, {row: 21, column: 1, colSpan: 2});
            this.__mlnFormContainer.add(this.__checkBoxSaveOutput, {row: 21, column: 3});
            this.__mlnFormContainer.add(this.__checkBoxUseAllCPU, {row: 22, column: 1});
            this.__mlnFormContainer.add(this.__checkBoxIgnoreUnknown, {row: 22, column: 2});
            this.__mlnFormContainer.add(this.__checkBoxShowLabels, {row: 22, column: 3});
            this.__mlnFormContainer.add(this.__buttonStart, {row: 23, column: 1, colSpan: 3});
            this._init();

            return mlnFormContainer;
        },

        /**
        * Update fields when changing the example folder
        */
        _change_example : function(e){
            var exampleFolder = e.getData()[0].getLabel();
            req = new qx.io.request.Xhr("/mln/_change_example", "POST");
            req.setRequestHeader("Content-Type", "application/json");
            req.setRequestData({"folder": exampleFolder});
            req.addListener("success", function(e) {
                var tar = e.getTarget();
                response = tar.getResponse();

                this.__selectMLN.removeAll();
                for (var i = 0; i < response.mlns.length; i++) {
                    this.__selectMLN.add(new qx.ui.form.ListItem(response.mlns[i]));
                }

                this.__selectEvidence.removeAll();
                for (var z = 0; z < response.dbs.length; z++) {
                    this.__selectEvidence.add(new qx.ui.form.ListItem(response.dbs[z]));
                }
            }, this);
            req.send();
        },

        /**
        * Show or hide fields for the mln model extension
        */
        _showModelExtension : function(e) {
            if (e.getData()) {
                this.__mlnFormContainer.add(this.__emlnLabel, {row: 7, column: 0});
                this.__mlnFormContainer.add(this.__selectEMLN, {row: 7, column: 1, colSpan: 3});
//                    this.__mlnFormContainer.add(this.__buttonSaveEMLN, {row: 7, column: 3});
                this.__mlnFormContainer.add(this.__emlnAreaContainer, {row: 8, column: 1, colSpan: 3});
//                    this.__mlnFormContainer.add(this.__checkBoxRenameEditEMLN, {row: 9, column: 1});
//                    this.__mlnFormContainer.add(this.__textFieldNameEMLN, {row: 10, column: 1, colSpan: 3});
                this.__mlnFormContainerLayout.setRowFlex(8, 1);

                var req = new qx.io.request.Xhr("/mln/_use_model_ext", "GET");
                req.addListener("success", function(e) {
                    var tar = e.getTarget();
                    var that = this;
                    response = tar.getResponse().split(",");
                    for (var i = 0; i < response.length; i++) {
                        that.__selectEMLN.add(new qx.ui.form.ListItem(response[i]));
                    }
                }, this);
                req.send();
            } else {
                this.__mlnFormContainer.remove(this.__emlnLabel);
                this.__mlnFormContainer.remove(this.__selectEMLN);
//                    this.__mlnFormContainer.remove(this.__buttonSaveEMLN);
                this.__mlnFormContainer.remove(this.__emlnAreaContainer);
//                    this.__mlnFormContainer.remove(this.__checkBoxRenameEditEMLN);
//                    this.__mlnFormContainer.remove(this.__textFieldNameEMLN);
                this.__mlnFormContainerLayout.setRowFlex(8, 0);
                this.__selectEMLN.removeAll();
                this.__textAreaEMLN.setValue("");
                this.__checkBoxRenameEditEMLN.setValue(false);
                this.__textFieldNameEMLN.setValue("");
            }
        },

        /**
        * Uploads a file to server and sets its content in the respective textarea
        */
        _upload : function(evt) {
            var file = evt.getData();
            var fileName = file.getFilename();
            console.log('uploading', fileName);
            this.__uploader.setAutoUpload(true);
            console.log('uploaded', fileName);
//            handler.beginUploads();
//            console.log('handler', handler);
//            file.setParam("MY_FILE_PARAM", "some-value");
//            var progressListenerId = file.addListener("changeProgress", function(evt) {
//                console.log("Upload " + file.getFilename() + ": " +
//                    evt.getData() + " / " + file.getSize() + " - " +
//                    Math.round(evt.getData() / file.getSize() * 100) + "%");
//            }, this);
        },

        /**
        * Start the inference process
        */
        _start_inference : function(e) {
                var that = this;

                var mln = (this.__selectMLN.getSelectables().length != 0) ? this.__selectMLN.getSelection()[0].getLabel() : "";
                var emln = (this.__selectEMLN.getSelectables().length != 0) ? this.__selectEMLN.getSelection()[0].getLabel() : "";
                var db = (this.__selectEvidence.getSelectables().length != 0) ? this.__selectEvidence.getSelection()[0].getLabel() : "";
                var method = (this.__selectMethod.getSelectables().length != 0) ? this.__selectMethod.getSelection()[0].getLabel() : "";
                var logic = (this.__selectLogic.getSelectables().length != 0) ? this.__selectLogic.getSelection()[0].getLabel() : "";
                var grammar = (this.__selectGrammar.getSelectables().length != 0) ? this.__selectGrammar.getSelection()[0].getLabel() : "";
                var mlnText = this.codeMirrormlnArea ? this.codeMirrormlnArea.doc.getValue() : "";
                var emlnText = this.codeMirroremlnArea ? this.codeMirroremlnArea.doc.getValue() : "";
                var dbText = this.codeMirrordbArea ? this.codeMirrordbArea.doc.getValue() : "";

                req = new qx.io.request.Xhr("/mln/_start_inference", "POST");
                req.setRequestHeader("Content-Type", "application/json");
                req.setRequestData({"mln": mln,
                                    "emln": emln,
                                    "db": db,
                                    "method": method,
                                    "logic": logic,
                                    "grammar": grammar,
                                    "mln_text": mlnText,
                                    "emln_text": emlnText,
                                    "db_text": dbText,
                                    "output": this.__textFieldOutput.getValue(),
                                    "params": this.__textFieldAddParams.getValue(),
                                    "mln_rename_on_edit": this.__checkBoxRenameEditMLN.getValue(),
                                    "db_rename_on_edit": this.__checkBoxRenameEditEvidence.getValue(),
                                    "query": this.__textFieldQueries.getValue(),
                                    "closed_world": this.__checkBoxApplyCWOption.getValue(),
                                    "cw_preds": this.__textFieldCWPreds.getValue(),
                                    "use_emln": this.__checkBoxUseModelExt.getValue(),
                                    "verbose": this.__textFieldVerbose.getValue(),
                                    "ignore_unknown_preds": this.__checkBoxIgnoreUnknown.getValue(),
                                    "save_results": this.__checkBoxSaveOutput.getValue(),
                                    "use_multicpu": this.__checkBoxUseAllCPU.getValue()});
                req.addListener("success", function(e) {
                        var that = this;
                        var tar = e.getTarget();
                        response = tar.getResponse();

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
                                        var link = new Object();
                                        link.source = formulaAtoms[i][j];
                                        link.target = formulaAtoms[i][k];
                                        link.value = [formulas[i]];
                                        link.arcStyle = "strokegreen";
                                        addList.push(link);
                                    }
                                }
                            }
                        }
                        that.updateGraph([],addList);
                        if (that.check) {
                            that.updateBarChart(resultsMap);
                        } else {
                            that.check = true;
                            that.d3BarChart(resultsMap);
                        }
                        that.__textAreaResults.setValue(output);
                        that.__textAreaResults.getContentElement().scrollToY(10000);

                }, this);
                req.send();
        },


        /**
        * Fetch options to choose from
        */
        _init : function() {
            req = new qx.io.request.Xhr("/mln/_init", "GET");
            req.addListener("success", function(e) {
                    var tar = e.getTarget();
                    var response = tar.getResponse();
                    for (var i = 0; i < response.examples.length; i++) {
                         this.__selectExampleFolder.add(new qx.ui.form.ListItem(response.examples[i]));
                    }

                    this.__textFieldQueries.setValue(response.queries);

                    var arr = ['files', 'infMethods', 'dbs'];
                    for (var x = 0; x < arr.length; x++) {
                        for (var i = 0; i < response[arr[x]].length; i++) {
                            (arr[x] == 'files' ? this.__selectMLN : arr[x] ==
                             'infMethods' ? this.__selectMethod :
                             this.__selectEvidence).add(new qx.ui.form.ListItem(response[arr[x]][i]));
                        }
                    }
            }, this);
            req.send();
        },

        /**
        * formatting template for inf settings labels and text
        */
        _template : function(val, type) {
        if (type === 'label')
            return '<span style="font-size:13px; font-weight:bold">' + val + '</span>'
        else
            return '<b>' + val + '</b>';
        },


        /**
        * trigger graph update
        */
        updateGraph : function(removeLinks, addLinks) {
          this._graph.updateData(removeLinks, addLinks);
        },

        /**
        * Creates new instance of graph if not existent, otherwise resets it
        */
        loadGraph : function() {
          if (typeof this._graph === 'undefined') {
            this._graph = new webmln.Graph();
          }
          this._graph.clear();
        },

        /**
        * Creates new lists of links to be removed and added for redrawing graph
        * this is only needed for a visible redrawing. To directly update graph,
        * use replaceData function in graph.
        */
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

        /**
        * Syntax highlighting
        */
        _highlight : function(id) {
            var code = CodeMirror.fromTextArea(document.getElementById(id), {
                lineNumbers: true
            });

            // save codemirror to be able to get the content later
            this['codeMirror' + id] = code;
        },

        /**
        * Update mln text field
        */
        _update_mln_text : function(e) {
            if (e.getData().length > 0) {
                var selection = e.getData()[0].getLabel();
                this._update_text(selection, this.__textAreaMLN);
            } else {
                this.__textAreaMLN.setValue('');
            }
        },

        /**
        * Update emln text field
        */
        _update_emln_text : function(e) {
            this._highlight('emlnArea');
        },

        /**
        * Update evidence text field
        */
        _update_evidence_text : function(e) {
            if (e.getData().length > 0) {
                 var selection = e.getData()[0].getLabel();
                 this._update_text(selection, this.__textAreaEvidence);
            } else {
                this.__textAreaEvidence.setValue('');
            }
        },

        /**
        * Replace text of given area with filecontent
        */
        _update_text : function(selection, area) {
            var that = this;
            var folder = this.__selectExampleFolder.getSelection()[0].getLabel();
            var req = new qx.io.request.Xhr();
            req.setUrl("/mln/_get_filecontent");
            req.setMethod('POST');
            req.setRequestHeader("Cache-Control", "no-cache");
            req.setRequestHeader("Content-Type", 'application/json');
            req.setRequestData({ "example": folder , "filename": selection });
            req.addListener("success", function(e) {
                var tar = e.getTarget();
                var response = tar.getResponse();
                area.setValue(response.text);
                this._highlight(area.getContentElement().getAttribute('id'));
                return;
            }, this);
            req.send();
        },

        /**
        * update selection items in expert settings
        */
        _update_selections : function(data) {
            // update kb selections
            this.kbSelect.removeAll();
            for (var k = 0; k < data.kblist.length; k++) {
                this.kbSelect.add(new qx.ui.form.ListItem(data.kblist[k]));
            }

            // update mln selections
            this.mlnSelect.removeAll();
            for (var m = 0; m < data.mlnlist.length; m++) {
                 this.mlnSelect.add(new qx.ui.form.ListItem(data.mlnlist[m]));
            }

            // update evidence selections
            this.evidenceSelect.removeAll();
            for (var e = 0; e < data.evidencelist.length; e++) {
                this.evidenceSelect.add(new qx.ui.form.ListItem(data.evidencelist[e]));
            }
        },


        d3BarChart : function(results) {
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
