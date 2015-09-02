/* ************************************************************************
   Copyright:
   License:
   Authors:
************************************************************************ */

/**
 * This is the main application class of your custom application "webmln"
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

            // destroy the session before leaving MLN
            window.onbeforeunload = function () {
            var req = new qx.io.request.Xhr();
            req.setUrl("/mln/_destroy_session");
            req.setMethod("POST");
            req.addListener("success", function(e) {
                var tar = e.getTarget();
                var response = tar.getResponse();
                var sessionname = response;
            });
            req.send();
            };

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
            var splitPaneInference = this.getsplitPaneInference();
            var splitPaneLearning = this.getsplitPaneLearning();

            var tabView = new qx.ui.tabview.TabView('bottom');
            tabView.setContentPadding(2,2,2,2);
            this.__tabView = tabView;

            ////////////////// INFERENCE PAGE ////////////////////
            var inferencePage = new qx.ui.tabview.Page("Inference");
            this.__inferencePage = inferencePage;
            inferencePage.setLayout(new qx.ui.layout.Grow());
            inferencePage.add(splitPaneInference, {width: "100%", height: "100%"});
            tabView.add(inferencePage, {width: "100%", height: "100%"});

            ////////////////// LEARNING PAGE ////////////////////
            var learningPage = new qx.ui.tabview.Page("Learning");
            this.__learningPage = learningPage;
            learningPage.addListener("appear", function(e) {
                                // todo prettify. this is a dirty hack as the
                                // highlighting does not work properly when the textareas
                                // are not yet created
                                this._highlight('tDataArea');
                                this._highlight('mlnLArea');
                                this._highlight('mlnResultArea');
                            }, this);
            learningPage.setLayout(new qx.ui.layout.Grow());
            learningPage.add(splitPaneLearning, {width: "100%", height: "100%"});
            tabView.add(learningPage, {width: "100%", height: "100%"});

            ////////////////// DOKU PAGE ////////////////////
            var aboutPage = new qx.ui.tabview.Page("Documentation");
            this.__aboutPage = aboutPage;
            var iframe = new qx.ui.embed.Iframe("/mln/doc/_build/html/index.html");
            aboutPage.setLayout(new qx.ui.layout.Grow());
            aboutPage.add(iframe);
            tabView.add(aboutPage, {width: "100%", height: "100%"});

            outerContainer.add(tabView, {width: "100%", height: "100%"});
            contentIsle.add(outerContainer, {width: "100%", height: "100%"});
            this._init();
        },


        /**
         * show or hide animated wait logo
         */
        _show_wait_animation : function(task, wait) {
            if (wait){
                this["_waitImage" + task].show();
            } else {
                this["_waitImage" + task].hide();
            }
        },


        /**
        * Build the outer splitpane containing the mln form and vizualization containers
        */
        getsplitPaneInference : function() {
            var waitImage = new qx.ui.basic.Image();
            waitImage.setSource('/mln/static/images/wait.gif');
            waitImage.getContentElement().setAttribute('id', 'waitImg');
            waitImage.setWidth(300);
            waitImage.setHeight(225);
            waitImage.setMarginLeft(-150);
            waitImage.setMarginTop(-125);
            waitImage.setScale(1);
            waitImage.hide();
            this._waitImageInf = waitImage;

            var textAreaResults = new qx.ui.form.TextArea("").set({
                font: qx.bom.Font.fromString("14px monospace")
            });
            this.__txtAResults = textAreaResults;
            textAreaResults.setReadOnly(true);

            var mlnFormContainer = this.buildMLNForm();
            this.__mlnFormContainer = mlnFormContainer;
            var splitPane = new qx.ui.splitpane.Pane("horizontal");
            var innerSplitPane = new qx.ui.splitpane.Pane("vertical");
            var innerMostSplitPane = new qx.ui.splitpane.Pane("vertical");
            var graphVizContainer = new qx.ui.container.Composite(new qx.ui.layout.Grow());
            graphVizContainer.setMinHeight(500);

            var vizEmbedGrp = new qx.ui.groupbox.GroupBox("Visualization");
            var vizLayout = new qx.ui.layout.Grow();
            vizEmbedGrp.setLayout(vizLayout);
            var vizHTML = "<div id='viz' style='width: 100%; height: 100%;'></div>";
            var vizEmbed = new qx.ui.embed.Html(vizHTML);
            vizEmbedGrp.add(vizEmbed);
            graphVizContainer.add(vizEmbedGrp, {width: "100%", height: "100%"});
            graphVizContainer.add(waitImage, { left: "50%", top: "50%"});

            var barChartContainer = new qx.ui.container.Composite(new qx.ui.layout.Grow());
            barChartContainer.getContentElement().setAttribute("id","dia");
            barChartContainer.getContentElement().setStyle("overflow","scroll",true);
            var diaEmbedGrp = new qx.ui.groupbox.GroupBox("Statistics");
            var diaLayout = new qx.ui.layout.Grow();
            diaEmbedGrp.setLayout(diaLayout);

            var diaContainer = new qx.ui.container.Composite(new qx.ui.layout.Grow());
            barChartContainer.addListener('resize', function(e) {
                    if (typeof this['_barChartdia'] != 'undefined') {
                      var vizSize = barChartContainer.getInnerSize();
                      this['_barChartdia'].w = vizSize.width;
                      // remove data and re-add it to trigger redrawing
                      var tempdata = this['_barChartdia'].barChartData.slice();
                      this['_barChartdia'].replaceData(tempdata);
                    }
            }, this);

            diaEmbedGrp.add(barChartContainer);
            diaContainer.add(diaEmbedGrp);
            innerMostSplitPane.add(diaContainer);
            innerMostSplitPane.add(textAreaResults);
            innerSplitPane.add(graphVizContainer);
            innerSplitPane.add(innerMostSplitPane);

            splitPane.add(mlnFormContainer, {width: "40%", height: "100%"});
            splitPane.add(innerSplitPane);

            return splitPane;

        },


        /**
        * Build the outer splitpane containing the mln form and vizualization containers
        */
        getsplitPaneLearning : function() {

            var waitImage = new qx.ui.basic.Image();
            waitImage.setSource('/mln/static/images/wait.gif');
            waitImage.getContentElement().setAttribute('id', 'waitImg');
            waitImage.setWidth(300);
            waitImage.setHeight(225);
            waitImage.setMarginLeft(-150);
            waitImage.setMarginTop(-125);
            waitImage.setScale(1);
            waitImage.hide();
            this._waitImageLrn = waitImage;

            var textAreaResults = new qx.ui.form.TextArea("").set({
                font: qx.bom.Font.fromString("14px monospace")
            });
            this.__txtAResults_Learning = textAreaResults;
            textAreaResults.setReadOnly(true);

            var mlnFormContainer = this.buildMLNLearningForm();
            this.__mlnFormContainer_L = mlnFormContainer;
            var splitPane = new qx.ui.splitpane.Pane("horizontal");
            var innerSplitPane = new qx.ui.splitpane.Pane("vertical");
            var innerMostSplitPane = new qx.ui.splitpane.Pane("vertical");
            var graphVizContainer = new qx.ui.container.Composite(new qx.ui.layout.Grow());
            graphVizContainer.setMinHeight(500);

            var vizEmbedGrp = new qx.ui.groupbox.GroupBox("Learned MLN");
            var vizLayout = new qx.ui.layout.Grow();
            vizEmbedGrp.setLayout(vizLayout);

            this.__txtAMLNviz = new qx.ui.form.TextArea("");
            this.__txtAMLNviz.getContentElement().setAttribute("id", 'mlnResultArea');
            vizEmbedGrp.add(this.__txtAMLNviz);

            var diaContainer = new qx.ui.container.Composite(new qx.ui.layout.Grow());

            var barChartContainer = new qx.ui.container.Composite(new qx.ui.layout.Grow());
            barChartContainer.getContentElement().setAttribute("id","diaL");
            barChartContainer.getContentElement().setStyle("overflow","scroll",true);
            var diaEmbedGrp = new qx.ui.groupbox.GroupBox("Statistics");
            var diaLayout = new qx.ui.layout.Grow();

            var diaContainer = new qx.ui.container.Composite(new qx.ui.layout.Grow());
            barChartContainer.addListener('resize', function(e) {
                    if (typeof this['_barChartdiaL'] != 'undefined') {
                      var vizSize = barChartContainer.getInnerSize();
                      this['_barChartdiaL'].w = vizSize.width;
//                      this['_barChartdiaL'].h = vizSize.height;
                      // remove data and re-add it to trigger redrawing
                      var tempdata = this['_barChartdiaL'].barChartData.slice();
                      this['_barChartdiaL'].replaceData(tempdata);
                    }
            }, this);

            diaEmbedGrp.setLayout(diaLayout);
            diaEmbedGrp.add(barChartContainer);
            graphVizContainer.add(vizEmbedGrp, {width: "100%", height: "100%"});
            graphVizContainer.add(waitImage, { left: "50%", top: "50%"});
            diaContainer.add(diaEmbedGrp);
            innerMostSplitPane.add(diaContainer);
            innerMostSplitPane.add(textAreaResults);
            innerSplitPane.add(graphVizContainer, { height: "50%"});
            innerSplitPane.add(innerMostSplitPane);

            splitPane.add(mlnFormContainer, {width: "40%", height: "100%"});
            splitPane.add(innerSplitPane);

            return splitPane;

        },


        /**
        * Build the query mln form
        */
        buildMLNForm : function() {

            this.check = false;
            var mlnFormContainerWSpacing = new qx.ui.container.Composite(new qx.ui.layout.VBox());
            mlnFormContainerWSpacing.add(new qx.ui.core.Spacer(10,80));

            var mlnFormContainerLayout = new qx.ui.layout.Grid();
            this.__mlnFormContainerLayout = mlnFormContainerLayout;
            mlnFormContainerLayout.setColumnWidth(0, 100);
            mlnFormContainerLayout.setColumnWidth(1, 130);
            mlnFormContainerLayout.setColumnWidth(2, 160);
            mlnFormContainerLayout.setColumnWidth(3, 110);
            mlnFormContainerLayout.setColumnWidth(4, 220);
            var mlnFormContainer = new qx.ui.container.Composite(mlnFormContainerLayout).set({
                    padding: 5
            });

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
            var addParamsLabel = new qx.ui.basic.Label().set({
                value: this._template('Params:', 'label'),
                rich : true
            });
            var cwPredsLabel = new qx.ui.basic.Label().set({
                value: this._template('CW Preds:', 'label'),
                rich : true
            });

            // widgets
            this.__slctXmplFldr = new qx.ui.form.SelectBox();
            this.__slctGrammar = new qx.ui.form.SelectBox();
            this.__slctLogic = new qx.ui.form.SelectBox();
            this.__slctMLN = new qx.ui.form.SelectBox();
            this.__btnRefreshMLN = new qx.ui.form.Button("<- refresh", null);
            this.__btnUploadMLNFile = new com.zenesis.qx.upload.UploadButton("Load MLN File");
            this.__btnUploadMLNFile.setParam("SOURCE_PARAM", "mlnuploadinf");
            this.__uploader = new com.zenesis.qx.upload.UploadMgr(this.__btnUploadMLNFile, "/mln/file_upload");
            this.__uploader.setAutoUpload(false);
            this.__chkbxRenameEditMLN = new qx.ui.form.CheckBox("rename on edit");
            this.__txtFNameMLN = new qx.ui.form.TextField("");
            this.__txtFNameMLN.setEnabled(false);
            this.__btnSaveMLN = new qx.ui.form.Button("save", null);

            var mlnAreaContainerLayout = new qx.ui.layout.Grow();
            this.__mlnAreaContainer = new qx.ui.container.Composite(mlnAreaContainerLayout);
            this.__txtAMLN = new qx.ui.form.TextArea("");
            this.__txtAMLN.getContentElement().setAttribute("id", 'mlnArea');
            this.__mlnAreaContainer.add(this.__txtAMLN);

            this.__chkbxUseModelExt = new qx.ui.form.CheckBox("use model extension");
            this.__slctEMLN = new qx.ui.form.SelectBox();
            this.__chkbxRenameEditEMLN = new qx.ui.form.CheckBox("rename on edit");
            this.__txtFNameEMLN = new qx.ui.form.TextField("");
            this.__txtFNameEMLN.setEnabled(false);
            this.__btnSaveEMLN = new qx.ui.form.Button("save",null);

            var emlnAreaContainerLayout = new qx.ui.layout.Grow();
            this.__emlnAreaContainer = new qx.ui.container.Composite(emlnAreaContainerLayout);
            this.__txtAEMLN = new qx.ui.form.TextArea("");
            this.__txtAEMLN.getContentElement().setAttribute("id", 'emlnArea');
            this.__emlnAreaContainer.add(this.__txtAEMLN);

            this.__slctEvidence = new qx.ui.form.SelectBox();
            this.__btnRefreshDB = new qx.ui.form.Button("<- refresh", null);
            this.__btnUploadDBFileInf = new com.zenesis.qx.upload.UploadButton("Load DB File");
            this.__btnUploadDBFileInf.setParam("SOURCE_PARAM", "dbuploadinf");
            this.__uploader.addWidget(this.__btnUploadDBFileInf)
            this.__chkbxRenameEditEvidence = new qx.ui.form.CheckBox("rename on edit");
            this.__txtFNameDB = new qx.ui.form.TextField("");
            this.__txtFNameDB.setEnabled(false);
            this.__btnSaveDB = new qx.ui.form.Button("save",null);

            var evidenceContainerLayout = new qx.ui.layout.Grow();
            this.__evidenceContainer = new qx.ui.container.Composite(evidenceContainerLayout);
            this.__txtAEvidence = new qx.ui.form.TextArea("");
            this.__txtAEvidence.getContentElement().setAttribute("id", 'dbArea');
            this.__evidenceContainer.add(this.__txtAEvidence);

            this.__slctMethod = new qx.ui.form.SelectBox();
            this.__txtFQueries = new qx.ui.form.TextField("");
            this.__chkbxVerbose = new qx.ui.form.CheckBox("verbose");
            this.__txtFCWPreds = new qx.ui.form.TextField("");
            this.__chkbxApplyCWOption = new qx.ui.form.CheckBox("Apply CW assumption to all but the query preds");
            this.__txtFParams = new qx.ui.form.TextField("");
            this.__chkbxUseAllCPU = new qx.ui.form.CheckBox("Use all CPUs");
            this.__chkbxIgnoreUnknown = new qx.ui.form.CheckBox("Ignore Unknown Predicates");
            this.__chkbxShowLabels = new qx.ui.form.CheckBox("Show Formulas");
            this.__btnStart = new qx.ui.form.Button("Start Inference", null);

            // add static listitems
            this.__slctGrammar.add(new qx.ui.form.ListItem("StandardGrammar"));
            this.__slctGrammar.add(new qx.ui.form.ListItem("PRACGrammar"));
            this.__slctLogic.add(new qx.ui.form.ListItem("FirstOrderLogic"));
            this.__slctLogic.add(new qx.ui.form.ListItem("FuzzyLogic"));

            // listeners
            this.__btnStart.addListener("execute", this._start_inference, this);
            this.__chkbxUseModelExt.addListener("changeValue", this._showModelExtension, this);
            this.__slctMLN.addListener("changeSelection", this._update_mln_text, this);
            this.__slctXmplFldr.addListener("changeSelection", this._change_example_inf ,this);
            this.__slctEvidence.addListener("changeSelection", this._update_evidence_text, this);
            this.__uploader.addListener("addFile", this._upload, this);
            this.__txtAEMLN.addListener("appear", this._update_emln_text, this);
            this.__chkbxShowLabels.addListener("changeValue", function(e) {
                            this._graph.showLabels(e.getData());
                        }, this);
            this.__chkbxRenameEditMLN.addListener("changeValue", function(e) {
                            this.__txtFNameMLN.setEnabled(e.getData());
                        }, this);
            this.__chkbxRenameEditEMLN.addListener("changeValue", function(e) {
                            this.__txtFNameEMLN.setEnabled(e.getData());
                        }, this);
            this.__chkbxRenameEditEvidence.addListener("changeValue", function(e) {
                            this.__txtFNameDB.setEnabled(e.getData());
                        }, this);                        
            this.__btnSaveMLN.addListener("execute", function(e) {
                            var name = this.__slctMLN.getSelection()[0].getLabel();
                            var newName = this.__chkbxRenameEditMLN ? this.__txtFNameMLN.getValue() : null;
                            var content = this.codeMirrormlnArea ? this.codeMirrormlnArea.doc.getValue() : "";
                            this._save_file(name, newName, content);
                        }, this);
            this.__btnSaveDB.addListener("execute", function(e) {
                            var name = this.__slctEvidence.getSelection()[0].getLabel();
                            var newName = this.__chkbxRenameEditEvidence ? this.__txtFNameDB.getValue() : null;
                            var content = this.codeMirrordbArea ? this.codeMirrordbArea.doc.getValue() : "";
                            this._save_file(name, newName, content);
                        }, this);
            this.__btnRefreshMLN.addListener("execute", function(e) {
                        this._refresh_list(this.__slctMLN, true);
                        },this);
            this.__btnRefreshDB.addListener("execute", function(e) {
                        this._refresh_list(this.__slctEvidence, false);
                        },this);


            // add widgets to form
            mlnFormContainer.add(exampleFolderLabel, {row: 0, column: 0});
            mlnFormContainer.add(grammarLabel, {row: 1, column: 0});
            mlnFormContainer.add(logicLabel, {row: 2, column: 0});
            mlnFormContainer.add(mlnLabel, {row: 3, column: 0});
            mlnFormContainer.add(evidenceLabel, {row: 11, column: 0});
            mlnFormContainer.add(methodLabel, {row: 15, column: 0});
            mlnFormContainer.add(queriesLabel, {row: 16, column: 0});
            mlnFormContainer.add(addParamsLabel, {row: 19, column: 0});
            mlnFormContainer.add(cwPredsLabel, {row: 20, column: 0});

            mlnFormContainer.add(this.__slctXmplFldr, {row: 0, column: 1, colSpan: 4});
            mlnFormContainer.add(this.__slctGrammar, {row: 1, column: 1, colSpan: 4});
            mlnFormContainer.add(this.__slctLogic, {row: 2, column: 1, colSpan: 4});
            mlnFormContainer.add(this.__slctMLN, {row: 3, column: 1, colSpan: 2});
            mlnFormContainer.add(this.__btnRefreshMLN, {row: 3, column: 3});
            mlnFormContainer.add(this.__btnUploadMLNFile, {row: 3, column: 4});
            mlnFormContainer.add(this.__mlnAreaContainer, {row: 4, column: 1, colSpan: 4});
            mlnFormContainerLayout.setRowHeight(4, 200);
            mlnFormContainer.add(this.__chkbxRenameEditMLN, {row: 5, column: 1});
            mlnFormContainer.add(this.__chkbxUseModelExt, {row: 5, column: 2});
            mlnFormContainer.add(this.__txtFNameMLN, {row: 6, column: 1, colSpan: 3});
            mlnFormContainer.add(this.__btnSaveMLN, {row: 6, column: 4});

            mlnFormContainer.add(this.__slctEvidence, {row: 11, column: 1, colSpan: 2});
            mlnFormContainer.add(this.__btnRefreshDB, {row: 11, column: 3});
            mlnFormContainer.add(this.__btnUploadDBFileInf, {row: 11, column: 4});
            mlnFormContainer.add(this.__evidenceContainer, {row: 12, column: 1, colSpan: 4});
            mlnFormContainerLayout.setRowHeight(12, 100);
            mlnFormContainer.add(this.__chkbxRenameEditEvidence, {row: 13, column: 1});
            mlnFormContainer.add(this.__txtFNameDB, {row: 14, column: 1, colSpan: 3});
            mlnFormContainer.add(this.__btnSaveDB, {row: 14, column: 4});
            mlnFormContainer.add(this.__slctMethod, {row: 15, column: 1, colSpan: 4});
            mlnFormContainer.add(this.__txtFQueries, {row: 16, column: 1, colSpan: 4});
            mlnFormContainer.add(this.__txtFParams, {row: 19, column: 1, colSpan: 4});
            mlnFormContainer.add(this.__txtFCWPreds, {row: 20, column: 1, colSpan: 2});
            mlnFormContainer.add(this.__chkbxApplyCWOption, {row: 20, column: 3, colSpan:2});
            mlnFormContainer.add(this.__chkbxUseAllCPU, {row: 22, column: 1});
            mlnFormContainer.add(this.__chkbxVerbose, {row: 22, column: 1});
            mlnFormContainer.add(this.__chkbxShowLabels, {row: 22, column: 2});
            mlnFormContainer.add(this.__chkbxIgnoreUnknown, {row: 22, column: 3, colSpan:2});
            mlnFormContainer.add(this.__btnStart, {row: 23, column: 1, colSpan: 4});

            mlnFormContainerWSpacing.add(mlnFormContainer);
            return mlnFormContainerWSpacing;
        },


        /**
        * Build the learning mln form
        */
        buildMLNLearningForm : function() {
            this.check = false;
            var mlnFormContainerWSpacing = new qx.ui.container.Composite(new qx.ui.layout.VBox());
            mlnFormContainerWSpacing.add(new qx.ui.core.Spacer(10,80));
            var mlnFormContainerLayout = new qx.ui.layout.Grid();
            mlnFormContainerLayout.setColumnWidth(0, 100);
            mlnFormContainerLayout.setColumnWidth(1, 130);
            mlnFormContainerLayout.setColumnWidth(2, 160);
            mlnFormContainerLayout.setColumnWidth(3, 110);
            mlnFormContainerLayout.setColumnWidth(4, 220);
            var mlnFormContainer = new qx.ui.container.Composite(mlnFormContainerLayout).set({
                    padding: 5
            });

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
            var trainingDataLabel = new qx.ui.basic.Label().set({
                value: this._template('Training Data:', 'label'),
                rich : true
            });
            var methodLabel = new qx.ui.basic.Label().set({
                value: this._template('Method:', 'label'),
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

            // widgets
            this.__slctXmplFldrLrn = new qx.ui.form.SelectBox();
            this.__btnUploadMLNFileLrn = new qx.ui.form.Button("Browse...", null);
            this.__slctGrammarLrn = new qx.ui.form.SelectBox();
            this.__slctLogicLrn = new qx.ui.form.SelectBox();
            this.__slctMLNLrn = new qx.ui.form.SelectBox();
            this.__btnRefreshMLNLrn = new qx.ui.form.Button("<- refresh", null);
            this.__btnUploadMLNFileLrn = new com.zenesis.qx.upload.UploadButton("Load MLN File");
            this.__btnUploadMLNFileLrn.setParam("SOURCE_PARAM", "mlnuploadlrn");
            this.__uploader.addWidget(this.__btnUploadMLNFileLrn);
            this.__btnSaveMLNLrn = new qx.ui.form.Button("save", null);

            var mlnAreaContainerLayout = new qx.ui.layout.Grow();
            this.__containerMLNAreaLrn = new qx.ui.container.Composite(mlnAreaContainerLayout);
            this.__txtAMLNLrn = new qx.ui.form.TextArea("");
            this.__txtAMLNLrn.getContentElement().setAttribute("id", 'mlnLArea');
            this.__containerMLNAreaLrn.add(this.__txtAMLNLrn);
            this.__chkbxRenameEditMLNLrn = new qx.ui.form.CheckBox("rename on edit");
            this.__txtFMLNNewNameLrn = new qx.ui.form.TextField("");
            this.__txtFMLNNewNameLrn.setEnabled(false);

            this.__slctMethodLrn = new qx.ui.form.SelectBox();
            this.__chkbxUsePrior = new qx.ui.form.CheckBox("use prior with mean of");
            this.__txtFMeanLrn = new qx.ui.form.TextField("");
            this.__txtFMeanLrn.setEnabled(false);
            var stdDevLabel = new qx.ui.basic.Label("and std dev of").set({alignX:'right', alignY:'middle',allowGrowX: false});
            this.__txtFStdDevLrn = new qx.ui.form.TextField("");
            this.__txtFStdDevLrn.setEnabled(false);
            this.__chkbxUseInitWeights = new qx.ui.form.CheckBox("use initial weights");
            this.__chkbxLearnIncrem = new qx.ui.form.CheckBox("learn incrementally");
            this.__chkbxShuffleDB = new qx.ui.form.CheckBox("shuffle databases");
            this.__chkbxShuffleDB.setEnabled(false);

            this.__radioQPreds = new qx.ui.form.RadioButton("Query preds:");
            this.__txtFQPredsLrn = new qx.ui.form.TextField("");
            this.__radioEPreds = new qx.ui.form.RadioButton("Evidence preds:");
            this.__txtFEPredsLrn = new qx.ui.form.TextField("");

            var radioBoxQPreds = new qx.ui.groupbox.RadioGroupBox("Query preds:");
            radioBoxQPreds.setContentPadding(0,0,0,0);
            radioBoxQPreds.setPadding(0,0,0,0);
            radioBoxQPreds.getChildControl("legend").setMarginTop(0);
            radioBoxQPreds.getChildControl("legend").setPaddingTop(0);
            radioBoxQPreds.getChildControl("legend").setTextColor('black');
            radioBoxQPreds.getChildControl("frame").setMarginTop(0);
            radioBoxQPreds.setLayout(new qx.ui.layout.VBox(0));
            radioBoxQPreds.add(this.__txtFQPredsLrn);

            var radioBoxEPreds = new qx.ui.groupbox.RadioGroupBox("Evidence preds:");
            radioBoxEPreds.setPadding(0,0,0,0);
            radioBoxEPreds.getChildControl("legend").setMargin(0);
            radioBoxEPreds.getChildControl("legend").setPadding(0);
            radioBoxEPreds.getChildControl("legend").setTextColor('black');
            radioBoxEPreds.getChildControl("legend").getContentElement().setAttribute('font-weight','normal');
            radioBoxEPreds.getChildControl("frame").setMargin(0);
            radioBoxEPreds.getChildControl("frame").setPadding(0);
            radioBoxEPreds.setLayout(new qx.ui.layout.VBox(0));
            radioBoxEPreds.add(this.__txtFEPredsLrn);

            new qx.ui.form.RadioGroup(radioBoxQPreds, radioBoxEPreds);

            this.__slctTDataLrn = new qx.ui.form.SelectBox();
            this.__btnRefreshTDataLrn = new qx.ui.form.Button("<- refresh", null);
            this.__btnUploadTDataFileLrn = new com.zenesis.qx.upload.UploadButton("Load DB File");
            this.__btnUploadTDataFileLrn.setParam("SOURCE_PARAM", "tdatauploadlrn");
            this.__uploader.addWidget(this.__btnUploadTDataFileLrn);
            this.__btnSaveTData = new qx.ui.form.Button("save", null);

            var tDataContainerLayout = new qx.ui.layout.Grow();
            this.__tDataContainer = new qx.ui.container.Composite(tDataContainerLayout);
            this.__txtATDataLrn = new qx.ui.form.TextArea("");
            this.__txtATDataLrn.getContentElement().setAttribute("id", 'tDataArea');
            this.__tDataContainer.add(this.__txtATDataLrn);
            this.__chkbxRenameEditTData = new qx.ui.form.CheckBox("rename on edit");
            this.__chkbxIgnoreUnknownLrn = new qx.ui.form.CheckBox("ignore unknown predicates");
            this.__txtFTDATANewNameLrn = new qx.ui.form.TextField("");
            this.__txtFTDATANewNameLrn.setEnabled(false);

            var orFilePatternLabel = new qx.ui.basic.Label("OR file pattern:");
            this.__txtFORFilePattern = new qx.ui.form.TextField("");
            this.__txtFParamsLrn = new qx.ui.form.TextField("");

            this.__chkbxUseAllCPULrn = new qx.ui.form.CheckBox("use all CPUs");
            this.__chkbxVerboseLrn = new qx.ui.form.CheckBox("verbose");
            this.__chkbxLRemoveFormulas = new qx.ui.form.CheckBox("remove 0-weight formulas");

            this.__btnStartLrn = new qx.ui.form.Button("Learn", null);

            // add static listitems
            this.__slctGrammarLrn.add(new qx.ui.form.ListItem("StandardGrammar"));
            this.__slctGrammarLrn.add(new qx.ui.form.ListItem("PRACGrammar"));
            this.__slctLogicLrn.add(new qx.ui.form.ListItem("FirstOrderLogic"));
            this.__slctLogicLrn.add(new qx.ui.form.ListItem("FuzzyLogic"));

            // listeners
            this.__slctXmplFldrLrn.addListener("changeSelection", this._change_example_lrn ,this);
            this.__btnStartLrn.addListener("execute", this._start_learning, this);
            this.__slctMLNLrn.addListener("changeSelection", this._update_mlnL_text, this);
            this.__slctTDataLrn.addListener("changeSelection", this._update_tData_text, this);
            this.__chkbxUsePrior.addListener("changeValue", function(e) {
                            this.__txtFMeanLrn.setEnabled(e.getData());
                            this.__txtFStdDevLrn.setEnabled(e.getData());
                        }, this);
            this.__chkbxRenameEditMLNLrn.addListener("changeValue", function(e) {
                            this.__txtFMLNNewNameLrn.setEnabled(e.getData());
                        }, this);
            this.__chkbxRenameEditTData.addListener("changeValue", function(e) {
                            this.__txtFTDATANewNameLrn.setEnabled(e.getData());
                        }, this);
            this.__btnSaveMLNLrn.addListener("execute", function(e) {
                            var name = this.__slctMLNLrn.getSelection()[0].getLabel();
                            var newName = this.__chkbxRenameEditMLNLrn ? this.__txtFMLNNewNameLrn.getValue() : null;
                            var content = this.codemirrormlnLArea ? this.codemirrormlnLArea.doc.getValue() : "";
                            this._save_file(name, newName, content);
                        }, this);
            this.__btnSaveTData.addListener("execute", function(e) {
                            var name = this.__slctTDataLrn.getSelection()[0].getLabel();
                            var newName = this.__chkbxRenameEditTData ? this.__txtFTDATANewNameLrn.getValue() : null;
                            var content = this.codeMirrortDataArea ? this.codeMirrortDataArea.doc.getValue() : "";
                            this._save_file(name, newName, content);
                        }, this);
            this.__btnRefreshMLNLrn.addListener("execute", function(e) {
                        this._refresh_list(this.__slctMLNLrn, true);
                        },this);
            this.__btnRefreshTDataLrn.addListener("execute", function(e) {
                        this._refresh_list(this.__slctTDataLrn, false);
                        },this);


            // add widgets to form
            mlnFormContainer.add(exampleFolderLabel, {row: 0, column: 0});
            mlnFormContainer.add(grammarLabel, {row: 1, column: 0});
            mlnFormContainer.add(logicLabel, {row: 2, column: 0});
            mlnFormContainer.add(mlnLabel, {row: 3, column: 0});
            mlnFormContainer.add(methodLabel, {row: 7, column: 0});
            mlnFormContainer.add(trainingDataLabel, {row: 12, column: 0});
            mlnFormContainer.add(addParamsLabel, {row: 17, column: 0});

            mlnFormContainer.add(this.__slctXmplFldrLrn, {row: 0, column: 1, colSpan: 4});
            mlnFormContainer.add(this.__slctGrammarLrn, {row: 1, column: 1, colSpan: 4});
            mlnFormContainer.add(this.__slctLogicLrn, {row: 2, column: 1, colSpan: 4});
            mlnFormContainer.add(this.__slctMLNLrn, {row: 3, column: 1, colSpan: 2});
            mlnFormContainer.add(this.__btnRefreshMLNLrn, {row: 3, column: 3});
            mlnFormContainer.add(this.__btnUploadMLNFileLrn, {row: 3, column: 4});
            mlnFormContainer.add(this.__containerMLNAreaLrn, {row: 4, column: 1, colSpan: 4});
            mlnFormContainerLayout.setRowHeight(4, 200);
            mlnFormContainer.add(this.__chkbxRenameEditMLNLrn, {row: 5, column: 1});
            mlnFormContainer.add(this.__txtFMLNNewNameLrn, {row: 6, column: 1, colSpan: 3});
            mlnFormContainer.add(this.__btnSaveMLNLrn, {row: 6, column: 4});
            mlnFormContainer.add(this.__slctMethodLrn, {row: 7, column: 1, colSpan: 4});
            mlnFormContainer.add(this.__chkbxUsePrior, {row: 8, column: 1});
            mlnFormContainer.add(this.__txtFMeanLrn, {row: 8, column: 2});
            mlnFormContainer.add(stdDevLabel, {row: 8, column: 3});
            mlnFormContainer.add(this.__txtFStdDevLrn, {row: 8, column: 4});
            mlnFormContainer.add(this.__chkbxUseInitWeights, {row: 9, column: 1});
            mlnFormContainer.add(this.__chkbxLearnIncrem, {row: 9, column: 2});
            mlnFormContainer.add(this.__chkbxShuffleDB, {row: 9, column: 3});
            mlnFormContainer.add(radioBoxQPreds, {row: 10, column: 1, colSpan: 2});
            mlnFormContainer.add(radioBoxEPreds, {row: 10, column: 3, colSpan: 2});
            mlnFormContainer.add(this.__slctTDataLrn, {row: 12, column: 1, colSpan: 2});
            mlnFormContainer.add(this.__btnRefreshTDataLrn, {row: 12, column: 3});
            mlnFormContainer.add(this.__btnUploadTDataFileLrn, {row: 12, column: 4});
            mlnFormContainer.add(this.__tDataContainer, {row: 13, column: 1, colSpan: 4});
            mlnFormContainerLayout.setRowHeight(13, 200);
            mlnFormContainer.add(this.__chkbxRenameEditTData, {row: 14, column: 1});
            mlnFormContainer.add(this.__chkbxIgnoreUnknownLrn, {row: 14, column: 2});
            mlnFormContainer.add(this.__txtFTDATANewNameLrn, {row: 15, column: 1, colSpan: 3});
            mlnFormContainer.add(this.__btnSaveTData, {row: 15, column: 4});
            mlnFormContainer.add(orFilePatternLabel, {row: 16, column: 1});
            mlnFormContainer.add(this.__txtFORFilePattern, {row: 16, column: 2, colSpan: 3});
            mlnFormContainer.add(this.__txtFParamsLrn, {row: 17, column: 1, colSpan: 4});
            mlnFormContainer.add(this.__chkbxUseAllCPU, {row: 18, column: 1});
            mlnFormContainer.add(this.__chkbxVerboseLrn, {row: 18, column: 2});
            mlnFormContainer.add(this.__chkbxLRemoveFormulas, {row: 18, column: 3, colSpan:2});
            mlnFormContainer.add(this.__btnStartLrn, {row: 20, column: 1, colSpan: 4});

            mlnFormContainerWSpacing.add(mlnFormContainer);
            return mlnFormContainerWSpacing;
        },


        /**
        * Update fields when changing the example folder for learning
        */
        _refresh_list : function(field, mln){
            var exampleFolder = (this.__tabView.isSelected(this.__inferencePage) ? this.__slctXmplFldr : this.__slctXmplFldrLrn).getSelection()[0].getLabel();
            var url = "/mln/"+ (this.__tabView.isSelected(this.__inferencePage) ? 'inference' : 'learning') + "/_change_example";
            var req = new qx.io.request.Xhr(url, "POST");
            req.setRequestHeader("Content-Type", "application/json");
            req.setRequestData({"folder": exampleFolder});
            req.addListener("success", function(e) {
                var tar = e.getTarget();
                var response = tar.getResponse();
                var filesList = mln ? response.mlns : response.dbs;

                field.removeAll();
                for (var i = 0; i < filesList.length; i++) {
                    field.add(new qx.ui.form.ListItem(filesList[i]));
                }
            }, this);
            req.send();
        },


        /**
        * Save edited file
        */
        _save_file : function(fname, newname, fcontent) {
            var isInfPage = this.__tabView.isSelected(this.__inferencePage);
            var xmplFldrSlctn = (isInfPage ? this.__slctXmplFldr : this.__slctXmplFldrLrn).getSelection()[0].getLabel();

            var req = new qx.io.request.Xhr("/mln/save_edited_file", "POST");
            req.setRequestHeader("Content-Type", "application/json");
            req.setRequestData({"folder": xmplFldrSlctn, "fname": fname, "newfname": newname, "content": fcontent});
            req.addListener("success", function(e) {
                var tar = e.getTarget();
                var response = tar.getResponse();
            }, this);
            req.send();
        },


        /**
        * Update fields when changing the example folder for inference
        */
        _change_example_inf : function(e){
            var exampleFolder = e.getData()[0].getLabel();
            var req = new qx.io.request.Xhr("/mln/inference/_change_example", "POST");
            req.setRequestHeader("Content-Type", "application/json");
            req.setRequestData({"folder": exampleFolder});
            req.addListener("success", function(e) {
                var tar = e.getTarget();
                var response = tar.getResponse();

                this._set_config(true, response.infconfig, response.mlns, response.dbs, response.infmethods);
            }, this);
            req.send();
        },


        /**
        * Update fields when changing the example folder for learning
        */
        _change_example_lrn : function(e){
            var exampleFolder = e.getData()[0].getLabel();
            var req = new qx.io.request.Xhr("/mln/learning/_change_example", "POST");
            req.setRequestHeader("Content-Type", "application/json");
            req.setRequestData({"folder": exampleFolder});
            req.addListener("success", function(e) {
                var tar = e.getTarget();
                var response = tar.getResponse();

                this._set_config(false, response.lrnconfig, response.mlns, response.dbs, response.lrnmethods);
            }, this);
            req.send();
        },


        /**
        * Show or hide fields for the mln model extension
        */
        _showModelExtension : function(e) {
            if (e.getData()) {
                this.__mlnFormContainer.add(this.__emlnLabel, {row: 7, column: 0});
                this.__mlnFormContainer.add(this.__slctEMLN, {row: 7, column: 1, colSpan: 4});
                this.__mlnFormContainer.add(this.__emlnAreaContainer, {row: 8, column: 1, colSpan: 4});
                this.__mlnFormContainer.add(this.__chkbxRenameEditEMLN, {row: 9, column: 1});
                this.__mlnFormContainer.add(this.__txtFNameEMLN, {row: 10, column: 1, colSpan: 3});
                this.__mlnFormContainer.add(this.__btnSaveEMLN, {row: 10, column: 4});
                this.__mlnFormContainerLayout.setRowFlex(8, 1);

                var req = new qx.io.request.Xhr("/mln/inference/_use_model_ext", "GET");
                req.addListener("success", function(e) {
                    var tar = e.getTarget();
                    var that = this;
                    var response = tar.getResponse().split(",");
                    for (var i = 0; i < response.length; i++) {
                        that.__slctEMLN.add(new qx.ui.form.ListItem(response[i]));
                    }
                }, this);
                req.send();
            } else {
                this.__mlnFormContainer.remove(this.__emlnLabel);
                this.__mlnFormContainer.remove(this.__slctEMLN);
                this.__mlnFormContainer.remove(this.__btnSaveEMLN);
                this.__mlnFormContainer.remove(this.__emlnAreaContainer);
                this.__mlnFormContainer.remove(this.__chkbxRenameEditEMLN);
                this.__mlnFormContainer.remove(this.__txtFNameEMLN);
                this.__mlnFormContainerLayout.setRowFlex(8, 0);
                this.__slctEMLN.removeAll();
                this.__txtAEMLN.setValue("");
                this.__chkbxRenameEditEMLN.setValue(false);
                this.__txtFNameEMLN.setValue("");
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
                this.loadGraph();
                this.loadBarChart(this.__tabView.isSelected(this.__inferencePage) ? "dia" : "diaL" );
                var mln = (this.__slctMLN.getSelectables().length != 0) ? this.__slctMLN.getSelection()[0].getLabel() : "";
                var emln = (this.__slctEMLN.getSelectables().length != 0) ? this.__slctEMLN.getSelection()[0].getLabel() : "";
                var db = (this.__slctEvidence.getSelectables().length != 0) ? this.__slctEvidence.getSelection()[0].getLabel() : "";
                var method = (this.__slctMethod.getSelectables().length != 0) ? this.__slctMethod.getSelection()[0].getLabel() : "";
                var logic = (this.__slctLogic.getSelectables().length != 0) ? this.__slctLogic.getSelection()[0].getLabel() : "";
                var grammar = (this.__slctGrammar.getSelectables().length != 0) ? this.__slctGrammar.getSelection()[0].getLabel() : "";
                var mlnText = this.codeMirrormlnArea ? this.codeMirrormlnArea.doc.getValue() : "";
                var emlnText = this.codeMirroremlnArea ? this.codeMirroremlnArea.doc.getValue() : "";
                var dbText = this.codeMirrordbArea ? this.codeMirrordbArea.doc.getValue() : "";

                var req = new qx.io.request.Xhr("/mln/inference/_start_inference", "POST");
                req.setRequestHeader("Content-Type", "application/json");
                req.setRequestData({"mln": mln,
                                    "emln": emln,
                                    "db": db,
                                    "mln_text": mlnText,
                                    "db_text": dbText,
                                    "emln_text": emlnText,
                                    "method": method,
                                    "params": this.__txtFParams.getValue(),
                                    "mln_rename_on_edit": this.__chkbxRenameEditMLN.getValue(),
                                    "db_rename_on_edit": this.__chkbxRenameEditEvidence.getValue(),
                                    "query": this.__txtFQueries.getValue(),
                                    "closed_world": this.__chkbxApplyCWOption.getValue(),
                                    "cw_preds": this.__txtFCWPreds.getValue(),
                                    "use_emln": this.__chkbxUseModelExt.getValue(),
                                    "logic": logic,
                                    "grammar": grammar,
                                    "use_multicpu": this.__chkbxUseAllCPU.getValue(),
                                    "ignore_unknown_preds": this.__chkbxIgnoreUnknown.getValue(),
                                    "verbose": this.__chkbxVerbose.getValue()});
                req.addListener("success", function(e) {
                        var that = this;
                        var tar = e.getTarget();
                        var response = tar.getResponse();

                        var atoms = response.atoms;
                        var formulas = response.formulas;
                        var keys = response.resultkeys;
                        var values = response.resultvalues;
                        var resultsMap = new Object();
                        for (var i = 0; i < keys.length; i++) {
                                resultsMap[keys[i]] = values[i];
                        }
                        this.___barChartDiaData = resultsMap;
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

                        this['_barChartdia'].replaceData(this._preprocess_barchartdata(this.___barChartDiaData));
                        that.__txtAResults.setValue(output);
                        that.__txtAResults.getContentElement().scrollToY(10000);

                }, this);
                req.send();
        },


        /**
        *
        */
        _preprocess_barchartdata : function(results) {
            var data = [];
            for (var key in results) {
                if (results.hasOwnProperty(key)) {
                    var data1 = new Object();
                    data1.name = key;
                    data1.value = results[key];
                    data.push(data1);
                }
            }
            return data;
        },


        /**
        * Start the learning process
        */
        _start_learning : function(e) {
                this._show_wait_animation("Lrn", true);
                var that = this;
                this.loadGraph();
                var mln = (this.__slctMLNLrn.getSelectables().length != 0) ? this.__slctMLNLrn.getSelection()[0].getLabel() : "";
                var db = (this.__slctTDataLrn.getSelectables().length != 0) ? this.__slctTDataLrn.getSelection()[0].getLabel() : "";
                var method = (this.__slctMethodLrn.getSelectables().length != 0) ? this.__slctMethodLrn.getSelection()[0].getLabel() : "";
                var logic = (this.__slctLogicLrn.getSelectables().length != 0) ? this.__slctLogicLrn.getSelection()[0].getLabel() : "";
                var grammar = (this.__slctGrammarLrn.getSelectables().length != 0) ? this.__slctGrammarLrn.getSelection()[0].getLabel() : "";
                var mlnText = this.codemirrormlnLArea ? this.codemirrormlnLArea.doc.getValue() : "";
                var dbText = this.codeMirrortDataArea ? this.codeMirrortDataArea.doc.getValue() : "";

                var req = new qx.io.request.Xhr("/mln/learning/_start_learning", "POST");
                req.setRequestHeader("Content-Type", "application/json");
                req.setRequestData({"mln": mln,
                                    "db": db,
                                    "mln_text": mlnText,
                                    "db_text": dbText,
                                    "method": method,
                                    "mln_rename_on_edit": this.__chkbxRenameEditMLNLrn.getValue(),
                                    "db_rename_on_edit": this.__chkbxRenameEditTData.getValue(),
                                    "params": this.__txtFParamsLrn.getValue(),
                                    "verbose": this.__chkbxVerboseLrn.getValue(),
                                    "pattern": this.__txtFORFilePattern.getValue(),
                                    "use_prior": this.__chkbxUsePrior.getValue(),
                                    "prior_mean": this.__txtFMeanLrn.getValue(),
                                    "prior_stdev": this.__txtFStdDevLrn.getValue(),
                                    "incremental": this.__chkbxLearnIncrem.getValue(),
                                    "shuffle": this.__chkbxShuffleDB.getValue(),
                                    "init_weights": this.__chkbxUseInitWeights.getValue(),
                                    "qpreds": this.__txtFQPredsLrn.getValue(),
                                    "epreds": this.__txtFEPredsLrn.getValue(),
                                    "discr_preds": this.__radioQPreds.getValue(),
                                    "logic": logic,
                                    "grammar": grammar,
                                    "multicore": this.__chkbxUseAllCPULrn.getValue(),
                                    "ignore_unknown_preds": this.__chkbxIgnoreUnknownLrn.getValue(),
                                    "ignore_zero_weight_formulas": this.__chkbxLRemoveFormulas.getValue()
                                    });
                req.addListener("success", function(e) {
                        this._show_wait_animation("Lrn", false);
                        var tar = e.getTarget();
                        var response = tar.getResponse();
                        var output = response.output;
                        this.__txtAMLNviz.setValue(response.learnedmln);
                        this._highlight('mlnResultArea');
                        this.__txtAResults_Learning.setValue(output);

                }, this);
                req.send();
        },


        /**
        * Fetch options to choose from
        */
        _init : function() {
            var req = new qx.io.request.Xhr("/mln/_init", "GET");
            req.addListener("success", function(e) {
                    var tar = e.getTarget();
                    var response = tar.getResponse();
                    var infconfig = response.inference.config;
                    var lrnconfig = response.learning.config;

                    // set examples for inference and learning
                    for (var i = 0; i < response.examples.length; i++) {
                         this.__slctXmplFldr.add(new qx.ui.form.ListItem(response.examples[i]));
                         this.__slctXmplFldrLrn.add(new qx.ui.form.ListItem(response.examples[i]));
                    }
            }, this);
            req.send();
        },


        /**
        * Set options according to loaded configuration
        */
        _set_config : function (isinfpage, config, mlnfiles, dbfiles, methods) {
            if (isinfpage) {
                // set mln files for inference
                this.__slctMLN.removeAll();
                for (var i = 0; i < mlnfiles.length; i++) {
                    if (mlnfiles[i] == config.mln) {
                        var selectedmlnitem = new qx.ui.form.ListItem(mlnfiles[i]);
                        this.__slctMLN.add(selectedmlnitem);
                    } else {
                        this.__slctMLN.add(new qx.ui.form.ListItem(mlnfiles[i]));
                    }
                }
                this.__slctMLN.setSelection(selectedmlnitem ? [selectedmlnitem] : []);

                // set db files for inference
                this.__slctEvidence.removeAll();
                for (var i = 0; i < dbfiles.length; i++) {
                    if (dbfiles[i] == config.db) {
                        var selectedevidenceitem = new qx.ui.form.ListItem(dbfiles[i]);
                        this.__slctEvidence.add(selectedevidenceitem);
                    } else {
                        this.__slctEvidence.add(new qx.ui.form.ListItem(dbfiles[i]));
                    }
                }
                this.__slctEvidence.setSelection(selectedevidenceitem ? [selectedevidenceitem] : []);

                // set inference methods and set selected from config
                this.__slctMethod.removeAll();
                for (var i = 0; i < methods.length; i++) {
                    if (methods[i] == config.method) {
                        var selectedmethoditem = new qx.ui.form.ListItem(methods[i]);
                        this.__slctMethod.add(selectedmethoditem);
                    } else {
                        this.__slctMethod.add(new qx.ui.form.ListItem(methods[i]));
                    }
                }
                this.__slctMethod.setSelection(selectedmethoditem ? [selectedmethoditem] : []);

                // set config for inference
                this.__chkbxApplyCWOption.setValue(config.cw || false);
                this.__txtFParams.setValue(config.params || '');
                this.__txtFQueries.setValue(config.queries || '');
                this.__chkbxVerbose.setValue(config.verbose || false);
                this.__chkbxUseAllCPU.setValue(config.multicore || false);

            } else {
                // set mln files for learning
                this.__slctMLNLrn.removeAll();
                for (var i = 0; i < mlnfiles.length; i++) {
                    if (mlnfiles[i] == config.mln) {
                        var selectedmlnitem = new qx.ui.form.ListItem(mlnfiles[i]);
                        this.__slctMLNLrn.add(selectedmlnitem);
                    } else {
                        this.__slctMLNLrn.add(new qx.ui.form.ListItem(mlnfiles[i]));
                    }
                }
                this.__slctMLNLrn.setSelection(selectedmlnitem ? [selectedmlnitem] : []);

                // set db files for learning
                this.__slctTDataLrn.removeAll();
                for (var i = 0; i < dbfiles.length; i++) {
                    if (dbfiles[i] == config.db) {
                        var selectedevidenceitem = new qx.ui.form.ListItem(dbfiles[i]);
                        this.__slctTDataLrn.add(selectedevidenceitem);
                    } else {
                        this.__slctTDataLrn.add(new qx.ui.form.ListItem(dbfiles[i]));
                    }
                }
                this.__slctTDataLrn.setSelection(selectedevidenceitem ? [selectedevidenceitem] : []);

                // set learning methods and set selected from config
                this.__slctMethodLrn.removeAll();
                for (var i = 0; i < methods.length; i++) {
                    console.log(methods[i],config.method,methods[i] == config.method);
                    if (methods[i] == config.method) {
                        var selectedmethoditem = new qx.ui.form.ListItem(methods[i]);
                        this.__slctMethodLrn.add(selectedmethoditem);
                    } else {
                        this.__slctMethodLrn.add(new qx.ui.form.ListItem(methods[i]));
                    }
                }
                this.__slctMethodLrn.setSelection(selectedmethoditem ? [selectedmethoditem] : []);

                // set config for learning
                this.__txtFParamsLrn.setValue(config.params || '');
                this.__chkbxVerboseLrn.setValue(config.verbose || false);
                this.__chkbxUseAllCPULrn.setValue(config.cw || false);
            }
        },


        /**
        * formatting template for inf settings labels and text
        */
        _template : function(val, type) {
        if (type === 'label')
            return '<span style="font-size:13px; font-weight:bold;">' + val + '</span>'
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
        * Creates new instance of graph if not existent, otherwise resets it
        */
        loadBarChart : function(id) {
          if (typeof this['_barChart' + id] === 'undefined') {
            this['_barChart' + id] = new webmln.BarChart(id);
          }
          this['_barChart' + id].clear();
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
            if (document.getElementById(id)) {
                var code = CodeMirror.fromTextArea(document.getElementById(id), {
                    lineNumbers: true
                });

                // save codemirror to be able to get the content later
                this['codeMirror' + id] = code;
            }
        },


        /**
        * Update mln text field
        */
        _update_mln_text : function(e) {
            if (e.getData().length > 0) {
                var selection = e.getData()[0].getLabel();
                this._update_text(selection, this.__txtAMLN);
            } else {
                this.__txtAMLN.setValue('');
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
                 this._update_text(selection, this.__txtAEvidence);
            } else {
                this.__txtAEvidence.setValue('');
            }
        },


        /**
        * Update mln text field for learning
        */
        _update_mlnL_text : function(e) {
            if (e.getData().length > 0) {
                var selection = e.getData()[0].getLabel();
                this._update_text(selection, this.__txtAMLNLrn);
            } else {
                this.__txtAMLNLrn.setValue('');
            }
        },


        /**
        * Update training data text field for learning
        */
        _update_tData_text : function(e) {
            if (e.getData().length > 0) {
                var selection = e.getData()[0].getLabel();
                this._update_text(selection, this.__txtATDataLrn);
            } else {
                this.__txtATDataLrn.setValue('');
            }
        },


        /**
        * Replace text of given area with filecontent
        */
        _update_text : function(selection, area) {
            var that = this;
            var folder = this.__slctXmplFldr.getSelection()[0].getLabel();
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
        }
    }
});
