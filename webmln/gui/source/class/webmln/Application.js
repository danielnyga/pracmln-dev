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
qx.Class.define("webmln.Application", {
	extend : qx.application.Inline,



    /*
      *****************************************************************************
         MEMBERS
      *****************************************************************************
      */

    members : {

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

            /* ********************** CREATE COMMON ELEMENTS ******************************/
            var mln_container = document.getElementById("mln_container", true, true);
            var contentIsle = new qx.ui.root.Inline(mln_container,true,true);
            this.__contentIsle = contentIsle;
            contentIsle.setWidth(document.getElementById("page", true, true).offsetWidth);
            contentIsle.setMaxWidth(document.getElementById("page", true, true).offsetWidth);
            contentIsle.setHeight(document.getElementById("page", true, true).offsetHeight);
            contentIsle.setMaxHeight(document.getElementById("page", true, true).offsetHeight);
            contentIsle.setLayout(new qx.ui.layout.Grow());

            // scrollable container
            var mainScrollContainer = new qx.ui.container.Scroll().set({
                width: 1024,
                height: 768
            });

            var canvascontainer = new qx.ui.container.Composite(new qx.ui.layout.Canvas());

            var tabView = new qx.ui.tabview.TabView('bottom');
            tabView.setContentPadding(2,2,2,2);
            this.__tabView = tabView;

            /* ************************ CREATE INFERENCE ELEMENTS **********************************/
            var containerinf = new qx.ui.container.Composite(new qx.ui.layout.HBox());

            // form
            var pracmlnlogo = new qx.ui.basic.Image('/mln/static/images/pracmln-logo.png');
            pracmlnlogo.setWidth(225);
            pracmlnlogo.setHeight(69);
            pracmlnlogo.setScale(1);
            var mlnforminf = this.buildMLNForm();
            var scroll =  new qx.ui.container.Scroll().set({
                width: 750
            });
            scroll.add(mlnforminf)
            var mlnformcontainerinf = new qx.ui.container.Composite(new qx.ui.layout.VBox());
            mlnformcontainerinf.add(pracmlnlogo);
            mlnformcontainerinf.add(scroll, {flex: 1});

            // visualization elements
            var vizEmbedGrp = new qx.ui.groupbox.GroupBox("Ground Markov Random Field");
            var vizLayout = new qx.ui.layout.Grow();
            vizEmbedGrp.setLayout(vizLayout);
            var vizHTML = "<div id='viz' style='width: 100%; height: 100%;'></div>";
            var vizEmbed = new qx.ui.embed.Html(vizHTML);
            vizEmbedGrp.add(vizEmbed);
            var waitImageInf = new qx.ui.basic.Image();
            waitImageInf.setSource('/mln/static/images/wait.gif');
            waitImageInf.setWidth(300);
            waitImageInf.setHeight(225);
            waitImageInf.setMarginLeft(-150);
            waitImageInf.setMarginTop(-125);
            waitImageInf.setScale(1);
            waitImageInf.hide();
            waitImageInf.getContentElement().setAttribute('id', 'waitImgInf');
            this._waitImageInf = waitImageInf;
            var legendImage = new qx.ui.basic.Image();
            legendImage.setSource('/mln/static/images/legend.png');
            legendImage.getContentElement().setAttribute('id', 'legend');
            legendImage.setWidth(56);
            legendImage.setHeight(37);
            legendImage.setScale(1);
            this._legendImage = legendImage;
            var graphVizContainerInf = new qx.ui.container.Composite(new qx.ui.layout.Canvas()).set({
                height: .5*document.getElementById("page", true, true).offsetHeight
            });

            var popup = new qx.ui.embed.Html();
            popup.setWidth(500);
            popup.setHeight(300);
            popup.setMarginLeft(-250);
            popup.setMarginTop(-150);
            popup.setOpacity(0);
            popup.hide();
            this._popup = popup;

            this._graphVizContainerInf = graphVizContainerInf;
            graphVizContainerInf.add(vizEmbedGrp, {width: "100%", height: "100%"});
            graphVizContainerInf.add(waitImageInf, { left: "50%", top: "50%"});
            graphVizContainerInf.add(legendImage, { left: 10, top: 25});


            // contains barchart svg
            var barChartContainer = new qx.ui.container.Composite(new qx.ui.layout.Grow());
            barChartContainer.getContentElement().setAttribute("id","dia");
            barChartContainer.getContentElement().setStyle("overflow","scroll",true);
            var diaEmbedGrp = new qx.ui.groupbox.GroupBox("Inference Result");
            var diaLayout = new qx.ui.layout.Grow();
            diaEmbedGrp.setLayout(diaLayout);
            diaEmbedGrp.add(barChartContainer);

            var textAreaResultsInf = new qx.ui.form.TextArea("").set({
                font: qx.bom.Font.fromString("14px monospace")
            });
            textAreaResultsInf.setReadOnly(true);
            this.__textAreaResultsInf = textAreaResultsInf;

            var innersplitpaneinf = new qx.ui.splitpane.Pane("vertical");
            innersplitpaneinf.setHeight(.5*document.getElementById("page", true, true).offsetHeight);
            innersplitpaneinf.add(diaEmbedGrp, 1);
            innersplitpaneinf.add(textAreaResultsInf, 2);
            var splitpaneinf = new qx.ui.splitpane.Pane("vertical");
            splitpaneinf.add(graphVizContainerInf, 0);
            splitpaneinf.add(innersplitpaneinf, 1);

            containerinf.add(mlnformcontainerinf);
            containerinf.add(splitpaneinf, {flex: 1});

            var condProb = new qx.ui.basic.Image();
            condProb.setAllowGrowX(true);
            condProb.setAllowShrinkX(true);
            condProb.setAllowGrowY(true);
            condProb.setAllowShrinkY(true);
            condProb.setScale(true);
            this._condProb = condProb;

            var condProbWin = new qx.ui.window.Window("Conditional Probability");
            condProbWin.setWidth(.2*document.getElementById("page", true, true).offsetWidth);
            condProbWin.setHeight(.1*document.getElementById("page", true, true).offsetWidth);
            condProbWin.setShowMinimize(false);
            condProbWin.setLayout(new qx.ui.layout.Canvas());
            condProbWin.setContentPadding(4);
            condProbWin.add(condProb);
            condProbWin.open();
            condProbWin.hide();
            this._condProbWin = condProbWin;

            /* ************************ CREATE LEARNING ELEMENTS **********************************/
            var containerlrn = new qx.ui.container.Composite(new qx.ui.layout.HBox());

            // form
            var pracmlnlogolrn = pracmlnlogo.clone();
            var mlnformlrn = this.buildMLNLearningForm();
            var scrolllrn =  new qx.ui.container.Scroll().set({
                width: 750
            });
            scrolllrn.add(mlnformlrn)
            var mlnformcontainerlrn = new qx.ui.container.Composite(new qx.ui.layout.VBox());
            mlnformcontainerlrn.add(pracmlnlogolrn);
            mlnformcontainerlrn.add(scrolllrn, {flex: 1});

            var vizEmbedGrpLrn = new qx.ui.groupbox.GroupBox("Learned MLN");
            var vizLayout = new qx.ui.layout.Grow();
            vizEmbedGrpLrn.setLayout(vizLayout);
            this._waitImageLrn = waitImageInf.clone();
            this._waitImageLrn.getContentElement().setAttribute('id', 'waitImgLrn');
            this.__txtAMLNviz = new qx.ui.form.TextArea("");
            this.__txtAMLNviz.getContentElement().setAttribute("id", 'mlnResultArea');
            vizEmbedGrpLrn.add(this.__txtAMLNviz);
            var graphVizContainerLrn = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
            this._graphVizContainerLrn = graphVizContainerLrn;
            graphVizContainerLrn.add(vizEmbedGrpLrn, { width: "100%", height: "100%"});
            graphVizContainerLrn.add(this._waitImageLrn, {left: "50%", top: "50%"});

            this.__txtAResultsLrn = this.__textAreaResultsInf.clone();

            var splitpanelrn = new qx.ui.splitpane.Pane("vertical");
            splitpanelrn.add(graphVizContainerLrn, 2);
            splitpanelrn.add(this.__txtAResultsLrn, 1);

            containerlrn.add(mlnformcontainerlrn);
            containerlrn.add(splitpanelrn, {flex: 1});

            /* ************************ LISTENERS **********************************/
            mln_container.addEventListener("resize", function() {
                var w = document.getElementById("page", true, true).offsetWidth;
                var h = document.getElementById("page", true, true).offsetHeight;
                contentIsle.setWidth(w);
                contentIsle.setHeight(h);
            }, this);

            document.addEventListener("roll", function(e) {
                this[0].scrollTop = this[0].scrollTop + e.delta.y;
                this[0].scrollLeft = this[0].scrollLeft + e.delta.x;
            }, this);

            window.addEventListener("resize", function() {
                var w = document.getElementById("page", true, true).offsetWidth;
                var h = document.getElementById("page", true, true).offsetHeight;
                contentIsle.setWidth(w);
                contentIsle.setHeight(h);
            }, this);

            // reposition graph when inference settings are shown/hidden
            graphVizContainerInf.addListener('resize', function(e) {
                if (typeof this._graph != 'undefined') {
                    var vizSize = graphVizContainerInf.getInnerSize();
                    var bounds = graphVizContainerInf.getBounds();
                    this._graph.w = vizSize.width;
                    this._graph.h = vizSize.height;
                    this._graph.update();
                }
            }, this);

            condProbWin.addListener("close", function() {
                this.__chkbxShowCondProb.setValue(false);
            }, this);

            // resize image to fit in window
            condProbWin.addListener("resize", function(e) {
            var ratio =  typeof this._imgRatio != 'undefined'? this._imgRatio : 1;
            var newWidth = e.getData().width - 10;
            var newHeight = e.getData().height - 30;
            if (newWidth / ratio <= newHeight) {
              newHeight = newWidth / ratio;
            } else {
              newWidth = newHeight * ratio;
            }
            condProb.setWidth(parseInt(newWidth, 10));
            condProb.setHeight(parseInt(newHeight, 10));
            }, this);

            // resize image to fit in window
            condProb.addListener("changeSource", function(e) {
            var ratio =  typeof this._imgRatio != 'undefined'? this._imgRatio : 1;
            var newWidth = condProbWin.getInnerSize().width - 10;
            var newHeight = condProbWin.getInnerSize().height - 30;
            if (newWidth / ratio <= newHeight) {
              newHeight = newWidth / ratio;
            } else {
              newWidth = newHeight * ratio;
            }
            condProb.setWidth(parseInt(newWidth, 10));
            condProb.setHeight(parseInt(newHeight, 10));
            }, this);

            barChartContainer.addListener('resize', function(e) {
                    if (typeof this['_barChartdia'] != 'undefined') {
                      var vizSize = barChartContainer.getInnerSize();
                      this['_barChartdia'].w = vizSize.width;
                      this['_barChartdia'].h = vizSize.height;
                      // remove data and re-add it to trigger redrawing
                      var tempdata = this['_barChartdia'].barChartData.slice();
                      this['_barChartdia'].replaceData(tempdata);
                    }
            }, this);


            /* ********************** SET UP LAYOUT ********************************/

            ////////////////// INFERENCE PAGE ////////////////////
            var inferencePage = new qx.ui.tabview.Page("Inference");
            this.__inferencePage = inferencePage;
            inferencePage.setLayout(new qx.ui.layout.Grow());
            inferencePage.add(containerinf, {width: "100%", height: "100%"});
            tabView.add(inferencePage, {width: "100%", height: "100%"});

            ////////////////// LEARNING PAGE ////////////////////
            var learningPage = new qx.ui.tabview.Page("Learning");
            this.__learningPage = learningPage;
            learningPage.addListener("appear", function(e) {
                                // todo prettify. this is a dirty hack as the
                                // highlighting does not work properly when the textareas
                                // are not yet created
                                this._highlight('tDataArea');
                                this._highlight('mlnAreaLrn');
                                this._highlight('mlnResultArea');
                            }, this);
            learningPage.setLayout(new qx.ui.layout.Grow());
            learningPage.add(containerlrn, {width: "100%", height: "100%"});
            tabView.add(learningPage, {width: "100%", height: "100%"});

            ////////////////// DOKU PAGE ////////////////////
            var aboutPage = new qx.ui.tabview.Page("Documentation");
            this.__aboutPage = aboutPage;
            var iframedocumentation = new qx.ui.embed.Iframe("/mln/doc/_build/html/mln_syntax.html");
            aboutPage.setLayout(new qx.ui.layout.Grow());
            aboutPage.add(iframedocumentation);
            tabView.add(aboutPage, {width: "100%", height: "100%"});

            canvascontainer.add(tabView, {width: "100%", height: "100%"});
            canvascontainer.add(popup, { left: "50%", top: "50%"});

            mainScrollContainer.add(canvascontainer, {width: "100%", height: "100%"});
            contentIsle.add(mainScrollContainer, {width: "100%", height: "100%"});
            this.getRoot().add(condProbWin, {left:20, top:20});
            this._init();
            this._send_user_stats();
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
         * show or hide message
         */
        _notify : function(message, delay, callback) {
            if (message && message != '') {
                var msg = '<div style="background-color: #bee280;"><center><h1>' + message + '</h1></center></div>';
                this._popup.setHtml(msg);

                var fadeIN = function(val, t) {
                    var fadeinInterval = setTimeout( function() {
                          if (val < 1.0) {
                            t._popup.setOpacity(val);
                            fadeIN(val + 0.1, t);
                          } else {
                            fadeOUT(1.0, t);
                          }
                    }, delay || 200);
                };

                var fadeOUT = function(val, t) {
                    var fadeoutInterval = setTimeout( function() {
                          if (val > 0.0) {
                            t._popup.setOpacity(val);
                            fadeOUT(val - 0.1, t);
                          } else {
                            t._popup.hide();
                            callback && callback.call(t||this);
                          }
                    }, delay || 200);
                };

                this._popup.show();
                fadeIN(0, this);
            }
        },


        /**
        * Build the query mln form
        */
        buildMLNForm : function() {
            this.check = false;

            var mlnFormContainerLayout = new qx.ui.layout.Grid();
            this.__mlnFormContainerLayout = mlnFormContainerLayout;
            mlnFormContainerLayout.setColumnWidth(0, 90);
            mlnFormContainerLayout.setColumnWidth(1, 130);
            mlnFormContainerLayout.setColumnWidth(2, 160);
            mlnFormContainerLayout.setColumnWidth(3, 110);
            mlnFormContainerLayout.setColumnWidth(4, 220);

            var mlnFormContainer = new qx.ui.container.Composite(mlnFormContainerLayout).set({
                    padding: 5
            });
            this.__mlnFormContainerInf = mlnFormContainer;

            // labels
            var exampleFolderLabel = new qx.ui.basic.Label().set({
                value: this._template('Project:', 'label'),
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
            this.__slctProjectInf = new qx.ui.form.SelectBox();
            this.__btnUploadProject = new com.zenesis.qx.upload.UploadButton("Upload Project");
            this.__btnUploadProject.setParam("SOURCE_PARAM", "INF");
            this.__projUploader = new com.zenesis.qx.upload.UploadMgr(this.__btnUploadProject, "/mln/proj_upload");
            this.__projUploader.setAutoUpload(false);

            this.__btnDownloadProj = new qx.ui.form.Button("Download Project", null);
            this.__slctGrammar = new qx.ui.form.SelectBox();
            this.__slctLogic = new qx.ui.form.SelectBox();
            this.__slctMLN = new qx.ui.form.SelectBox();

            this.__btnUploadMLNFile = new com.zenesis.qx.upload.UploadButton("Load MLN File");
            this.__btnUploadMLNFile.setParam("SOURCE_PARAM", "INFxMLN");
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
            this.__btnUploadDBFileInf = new com.zenesis.qx.upload.UploadButton("Load DB File");
            this.__btnUploadDBFileInf.setParam("SOURCE_PARAM", "INFxDB");
            this.__uploader.addWidget(this.__btnUploadDBFileInf)
            this.__chkbxRenameEditEvidence = new qx.ui.form.CheckBox("rename on edit");
            this.__chkbxShowCondProb = new qx.ui.form.CheckBox("show/hide cond. probability");
            this.__txtFTimeout = new qx.ui.form.TextField("");
            this.__txtFTimeout.setValue('120');
            this.__chkbxTimeout = new qx.ui.form.CheckBox("Timeout");
            this.__chkbxTimeout.setValue(1);
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
            this.__chkbxmulticore = new qx.ui.form.CheckBox("Use all CPUs");
            this.__chkbxIgnoreUnknown = new qx.ui.form.CheckBox("Ignore Unknown Predicates");
            this.__chkbxShowLabels = new qx.ui.form.CheckBox("Show Formulas");
            this.__btnStart = new qx.ui.form.Button("Start Inference", null);

            // add static listitems
            var sgrammar = new qx.ui.form.ListItem("StandardGrammar");
            var pgrammar = new qx.ui.form.ListItem("PRACGrammar");
            var fol = new qx.ui.form.ListItem("FirstOrderLogic");
            var fl = new qx.ui.form.ListItem("FuzzyLogic");
            this.__listitems = {'StandardGrammar': sgrammar, 'PRACGrammar': pgrammar,
                                'FirstOrderLogic': fol, 'FuzzyLogic': fl};
            this.__slctGrammar.add(this.__listitems['StandardGrammar']);
            this.__slctGrammar.add(this.__listitems['PRACGrammar']);
            this.__slctLogic.add(this.__listitems["FirstOrderLogic"]);
            this.__slctLogic.add(this.__listitems["FuzzyLogic"]);

            // listeners
            this.__slctEMLN.addListener("changeSelection", this._update_emln_text, this);
            this.__btnStart.addListener("execute", this._start_inference, this);
            this.__chkbxUseModelExt.addListener("changeValue", this._showModelExtension, this);
            this.__slctMLN.addListener("changeSelection", this._update_mln_text, this);
            this.__slctProjectInf.addListener("changeSelection", this._change_example_inf ,this);
            this.__slctEvidence.addListener("changeSelection", this._update_evidence_text, this);
            this.__uploader.addListener("addFile", this._upload, this);
            this.__projUploader.addListener("addFile", this._uploadProj, this);
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
                            var newName = this.__txtFNameMLN.getValue();
                            var content = this.codeMirrormlnArea ? this.codeMirrormlnArea.doc.getValue() : "";
                            var rename = this.__chkbxRenameEditMLN.getValue();
                            this._save_file(name, newName, rename, content);
                        }, this);
            this.__btnSaveDB.addListener("execute", function(e) {
                            var name = this.__slctEvidence.getSelection()[0].getLabel();
                            var newName = this.__txtFNameDB.getValue();
                            var content = this.codeMirrordbArea ? this.codeMirrordbArea.doc.getValue() : "";
                            var rename = this.__chkbxRenameEditEvidence.getValue();
                            this._save_file(name, newName, rename, content);
                        }, this);
            this.__chkbxShowCondProb.addListener('changeValue', function(e) {
                    e.getData() ? this._condProbWin.show() : this._condProbWin.hide();
                }, this);
            this.__btnDownloadProj.addListener('execute', function(e) {
                this._download_project();
            }, this);
            this.__txtFTimeout.addListener("keypress", function(e){
                // only accept digits in timeout textfield
                if(e.getKeyIdentifier().search(/^[0-9.,SpaceBackspaceDeleteLeftRight]+$/) == -1) {
                    e.preventDefault();
                }
            });
            this.__chkbxTimeout.addListener("changeEnabled", function(e){
                this.__txtFTimeout.setEnabled(e.getData());
            }, this);
            this.__chkbxTimeout.addListener("changeValue", function(e){
                this.__txtFTimeout.setEnabled(e.getData());
            }, this);
            this.__chkbxmulticore.addListener("changeValue", function(e){
                this.__chkbxTimeout.setEnabled(!e.getData());
            }, this);


            // add widgets to form
            var row = 0;
            mlnFormContainer.add(exampleFolderLabel, {row: row, column: 0});
            mlnFormContainer.add(this.__slctProjectInf, {row: row, column: 1, colSpan: 2});
            mlnFormContainer.add(this.__btnUploadProject, {row: row, column: 3});
            mlnFormContainer.add(this.__btnDownloadProj, {row: row, column: 4});
            row += 1;
            mlnFormContainer.add(grammarLabel, {row: row, column: 0});
            mlnFormContainer.add(this.__slctGrammar, {row: row, column: 1, colSpan: 4});
            row += 1;
            mlnFormContainer.add(logicLabel, {row: row, column: 0});
            mlnFormContainer.add(this.__slctLogic, {row: row, column: 1, colSpan: 4});
            row += 1;
            mlnFormContainer.add(mlnLabel, {row: row, column: 0});
            mlnFormContainer.add(this.__slctMLN, {row: row, column: 1, colSpan: 3});
            mlnFormContainer.add(this.__btnUploadMLNFile, {row: row, column: 4});
            row += 1;
            mlnFormContainer.add(this.__mlnAreaContainer, {row: row, column: 1, colSpan: 4});
            mlnFormContainerLayout.setRowHeight(4, 250);
            row += 1;
            mlnFormContainer.add(this.__chkbxRenameEditMLN, {row: row, column: 1});
            mlnFormContainer.add(this.__chkbxUseModelExt, {row: row, column: 2});
            row += 1;
            mlnFormContainer.add(this.__txtFNameMLN, {row: row, column: 1, colSpan: 3});
            mlnFormContainer.add(this.__btnSaveMLN, {row: row, column: 4});
            row += 1;
            this._rowmodelext = row;
            // leave rows 7 - 10 empty for expanding model extension!
            row += 4;
            mlnFormContainer.add(evidenceLabel, {row: row, column: 0});
            mlnFormContainer.add(this.__slctEvidence, {row: row, column: 1, colSpan: 3});
            mlnFormContainer.add(this.__btnUploadDBFileInf, {row: row, column: 4});
            row += 1;
            mlnFormContainer.add(this.__evidenceContainer, {row: row, column: 1, colSpan: 4});
            mlnFormContainerLayout.setRowHeight(row, 250);
            row += 1;
            mlnFormContainer.add(this.__chkbxRenameEditEvidence, {row: row, column: 1});
            mlnFormContainer.add(this.__chkbxShowCondProb, {row: row, column: 2});
            mlnFormContainer.add(this.__txtFTimeout, {row: row, column: 3});
            mlnFormContainer.add(this.__chkbxTimeout, {row: row, column: 4});
            row += 1;
            mlnFormContainer.add(this.__txtFNameDB, {row: row, column: 1, colSpan: 3});
            mlnFormContainer.add(this.__btnSaveDB, {row: row, column: 4});
            row += 1;
            mlnFormContainer.add(methodLabel, {row: row, column: 0});
            mlnFormContainer.add(this.__slctMethod, {row: row, column: 1, colSpan: 4});
            row += 1;
            mlnFormContainer.add(queriesLabel, {row: row, column: 0});
            mlnFormContainer.add(this.__txtFQueries, {row: row, column: 1, colSpan: 4});
            row += 1;
            mlnFormContainer.add(addParamsLabel, {row: row, column: 0});
            mlnFormContainer.add(this.__txtFParams, {row: row, column: 1, colSpan: 4});
            row += 1;
            mlnFormContainer.add(cwPredsLabel, {row: row, column: 0});
            mlnFormContainer.add(this.__txtFCWPreds, {row: row, column: 1, colSpan: 2});
            mlnFormContainer.add(this.__chkbxApplyCWOption, {row: row, column: 3, colSpan:2});
            row += 1;
            mlnFormContainer.add(this.__chkbxVerbose, {row: row, column: 1});
            mlnFormContainer.add(this.__chkbxShowLabels, {row: row, column: 2});
            mlnFormContainer.add(this.__chkbxmulticore, {row: row, column: 3});
            mlnFormContainer.add(this.__chkbxIgnoreUnknown, {row: row, column: 4});
            row += 1;
            mlnFormContainer.add(this.__btnStart, {row: row, column: 1, colSpan: 4});
            row += 1;

            return mlnFormContainer;
        },


        /**
        * Build the learning mln form
        */
        buildMLNLearningForm : function() {
            this.check = false;

            var mlnFormContainerLrnLayout = new qx.ui.layout.Grid();
            mlnFormContainerLrnLayout.setColumnWidth(0, 90);
            mlnFormContainerLrnLayout.setColumnWidth(1, 130);
            mlnFormContainerLrnLayout.setColumnWidth(2, 160);
            mlnFormContainerLrnLayout.setColumnWidth(3, 110);
            mlnFormContainerLrnLayout.setColumnWidth(4, 220);
            var mlnFormContainerLrn = new qx.ui.container.Composite(mlnFormContainerLrnLayout).set({
                    padding: 5
            });

            // labels
            var exampleFolderLabel = new qx.ui.basic.Label().set({
                value: this._template('Project:', 'label'),
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

            // widgets
            this.__slctProjectLrn = new qx.ui.form.SelectBox();
            this.__btnUploadProjectLrn = new com.zenesis.qx.upload.UploadButton("Upload Project");
            this.__btnUploadProjectLrn.setParam("SOURCE_PARAM", "LRN");
            this.__projUploader.addWidget(this.__btnUploadProjectLrn);
            this.__btnDownloadProjLrn = new qx.ui.form.Button("Download Project", null);

            this.__btnUploadMLNFileLrn = new qx.ui.form.Button("Browse...", null);
            this.__slctGrammarLrn = new qx.ui.form.SelectBox();
            this.__slctLogicLrn = new qx.ui.form.SelectBox();
            this.__slctMLNLrn = new qx.ui.form.SelectBox();
            this.__btnUploadMLNFileLrn = new com.zenesis.qx.upload.UploadButton("Load MLN File");
            this.__btnUploadMLNFileLrn.setParam("SOURCE_PARAM", "LRNxMLN");
            this.__uploader.addWidget(this.__btnUploadMLNFileLrn);
            this.__btnSaveMLNLrn = new qx.ui.form.Button("save", null);

            var mlnAreaContainerLayout = new qx.ui.layout.Grow();
            this.__containerMLNAreaLrn = new qx.ui.container.Composite(mlnAreaContainerLayout);
            this.__txtAMLNLrn = new qx.ui.form.TextArea("");
            this.__txtAMLNLrn.getContentElement().setAttribute("id", 'mlnAreaLrn');
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
            this.__btnUploadTDataFileLrn = new com.zenesis.qx.upload.UploadButton("Load DB File");
            this.__btnUploadTDataFileLrn.setParam("SOURCE_PARAM", "LRNxMLN");
            this.__uploader.addWidget(this.__btnUploadTDataFileLrn);
            this.__btnSaveTData = new qx.ui.form.Button("save", null);

            var tDataContainerLayout = new qx.ui.layout.Grow();
            this.__tDataContainer = new qx.ui.container.Composite(tDataContainerLayout);
            this.__txtATDataLrn = new qx.ui.form.TextArea("");
            this.__txtATDataLrn.getContentElement().setAttribute("id", 'tDataArea');
            this.__tDataContainer.add(this.__txtATDataLrn);
            this.__chkbxRenameEditTData = new qx.ui.form.CheckBox("rename on edit");
            this.__chkbxIgnoreUnknownLrn = new qx.ui.form.CheckBox("ignore unknown predicates");
            this.__txtFTimeoutLrn = new qx.ui.form.TextField("");
            this.__txtFTimeoutLrn.setValue('120');
            this.__chkbxTimeoutLrn = new qx.ui.form.CheckBox("Timeout");
            this.__chkbxTimeoutLrn.setValue(1);
            this.__txtFTDATANewNameLrn = new qx.ui.form.TextField("");
            this.__txtFTDATANewNameLrn.setEnabled(false);

            var orFilePatternLabel = new qx.ui.basic.Label("OR file pattern:");
            this.__txtFORFilePattern = new qx.ui.form.TextField("");
            this.__txtFParamsLrn = new qx.ui.form.TextField("");

            this.__chkbxmulticoreLrn = new qx.ui.form.CheckBox("use all CPUs");
            this.__chkbxVerboseLrn = new qx.ui.form.CheckBox("verbose");
            this.__chkbxLRemoveFormulas = new qx.ui.form.CheckBox("remove 0-weight formulas");

            this.__btnStartLrn = new qx.ui.form.Button("Learn", null);

            // add static listitems
            var sgrammar = new qx.ui.form.ListItem("StandardGrammar");
            var pgrammar = new qx.ui.form.ListItem("PRACGrammar");
            var fol = new qx.ui.form.ListItem("FirstOrderLogic");
            var fl = new qx.ui.form.ListItem("FuzzyLogic");
            this.__listitemsLrn = {'StandardGrammar': sgrammar, 'PRACGrammar': pgrammar,
                                'FirstOrderLogic': fol, 'FuzzyLogic': fl};
            this.__slctGrammarLrn.add(this.__listitemsLrn["StandardGrammar"]);
            this.__slctGrammarLrn.add(this.__listitemsLrn["PRACGrammar"]);
            this.__slctLogicLrn.add(this.__listitemsLrn["FirstOrderLogic"]);
            this.__slctLogicLrn.add(this.__listitemsLrn["FuzzyLogic"]);

            // listeners
            this.__slctProjectLrn.addListener("changeSelection", this._change_example_lrn ,this);
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
                            var newName = this.__txtFMLNNewNameLrn.getValue();
                            var content = this.codeMirrormlnAreaLrn ? this.codeMirrormlnAreaLrn.doc.getValue() : "";
                            var rename = this.__chkbxRenameEditMLNLrn.getValue();
                            this._save_file(name, newName, rename, content);
                        }, this);
            this.__btnSaveTData.addListener("execute", function(e) {
                            var name = this.__slctTDataLrn.getSelection()[0].getLabel();
                            var newName = this.__txtFTDATANewNameLrn.getValue();
                            var content = this.codeMirrortDataArea ? this.codeMirrortDataArea.doc.getValue() : "";
                            var rename = this.__chkbxRenameEditTData.getValue();
                            this._save_file(name, newName, rename, content);
                        }, this);
            this.__btnDownloadProjLrn.addListener('execute', function(e) {
                this._download_project();
            }, this);
            this.__txtFTimeoutLrn.addListener("keypress", function(e){
                // only accept digits in timeout textfield
                if(e.getKeyIdentifier().search(/^[0-9.,SpaceBackspaceDeleteLeftRight]+$/) == -1) {
                    e.preventDefault();
                }
            });
            this.__chkbxTimeoutLrn.addListener("changeValue", function(e){
                this.__txtFTimeoutLrn.setEnabled(e.getData());
            }, this);
            this.__chkbxTimeoutLrn.addListener("changeEnabled", function(e){
                this.__txtFTimeoutLrn.setEnabled(e.getData());
            }, this);
            this.__chkbxmulticoreLrn.addListener("changeValue", function(e){
                this.__chkbxTimeoutLrn.setEnabled(!e.getData());
            }, this);


            // add widgets to form
            var row = 0;
            mlnFormContainerLrn.add(exampleFolderLabel, {row: row, column: 0});
            mlnFormContainerLrn.add(this.__slctProjectLrn, {row: row, column: 1, colSpan: 2});
            mlnFormContainerLrn.add(this.__btnUploadProjectLrn, {row: row, column: 3});
            mlnFormContainerLrn.add(this.__btnDownloadProjLrn, {row: row, column: 4});
            row += 1;
            mlnFormContainerLrn.add(grammarLabel, {row: row, column: 0});
            mlnFormContainerLrn.add(this.__slctGrammarLrn, {row: row, column: 1, colSpan: 4});
            row += 1;
            mlnFormContainerLrn.add(logicLabel, {row: row, column: 0});
            mlnFormContainerLrn.add(this.__slctLogicLrn, {row: 2, column: 1, colSpan: 4});
            row += 1;
            mlnFormContainerLrn.add(mlnLabel, {row: row, column: 0});
            mlnFormContainerLrn.add(this.__slctMLNLrn, {row: row, column: 1, colSpan: 3});
            mlnFormContainerLrn.add(this.__btnUploadMLNFileLrn, {row: row, column: 4});
            row += 1;
            mlnFormContainerLrn.add(this.__containerMLNAreaLrn, {row: row, column: 1, colSpan: 4});
            mlnFormContainerLrnLayout.setRowHeight(row, 250);
            row += 1;
            mlnFormContainerLrn.add(this.__chkbxRenameEditMLNLrn, {row: row, column: 1});
            row += 1;
            mlnFormContainerLrn.add(this.__txtFMLNNewNameLrn, {row: row, column: 1, colSpan: 3});
            mlnFormContainerLrn.add(this.__btnSaveMLNLrn, {row: row, column: 4});
            row += 1;
            mlnFormContainerLrn.add(methodLabel, {row: row, column: 0});
            mlnFormContainerLrn.add(this.__slctMethodLrn, {row: row, column: 1, colSpan: 4});
            row += 1;
            mlnFormContainerLrn.add(this.__chkbxUsePrior, {row: row, column: 1});
            mlnFormContainerLrn.add(this.__txtFMeanLrn, {row: row, column: 2});
            mlnFormContainerLrn.add(stdDevLabel, {row: row, column: 3});
            mlnFormContainerLrn.add(this.__txtFStdDevLrn, {row: row, column: 4});
            row += 1;
            mlnFormContainerLrn.add(this.__chkbxUseInitWeights, {row: row, column: 1});
            mlnFormContainerLrn.add(this.__chkbxLearnIncrem, {row: row, column: 2});
            mlnFormContainerLrn.add(this.__chkbxShuffleDB, {row: row, column: 3});
            row += 1;
            mlnFormContainerLrn.add(radioBoxQPreds, {row: row, column: 1, colSpan: 2});
            mlnFormContainerLrn.add(radioBoxEPreds, {row: row, column: 3, colSpan: 2});
            row += 1;
            mlnFormContainerLrn.add(trainingDataLabel, {row: row, column: 0});
            mlnFormContainerLrn.add(this.__slctTDataLrn, {row: row, column: 1, colSpan: 3});
            mlnFormContainerLrn.add(this.__btnUploadTDataFileLrn, {row: row, column: 4});
            row += 1;
            mlnFormContainerLrn.add(this.__tDataContainer, {row: row, column: 1, colSpan: 4});
            mlnFormContainerLrnLayout.setRowHeight(row, 250);
            row += 1;
            mlnFormContainerLrn.add(this.__chkbxRenameEditTData, {row: row, column: 1});
            mlnFormContainerLrn.add(this.__chkbxIgnoreUnknownLrn, {row: row, column: 2});
            mlnFormContainerLrn.add(this.__txtFTimeoutLrn, {row: row, column: 3});
            mlnFormContainerLrn.add(this.__chkbxTimeoutLrn, {row: row, column: 4});
            row += 1;
            mlnFormContainerLrn.add(this.__txtFTDATANewNameLrn, {row: row, column: 1, colSpan: 3});
            mlnFormContainerLrn.add(this.__btnSaveTData, {row: row, column: 4});
            row += 1;
            mlnFormContainerLrn.add(orFilePatternLabel, {row: row, column: 1});
            mlnFormContainerLrn.add(this.__txtFORFilePattern, {row: row, column: 2, colSpan: 3});
            row += 1;
            mlnFormContainerLrn.add(addParamsLabel, {row: row, column: 0});
            mlnFormContainerLrn.add(this.__txtFParamsLrn, {row: row, column: 1, colSpan: 4});
            row += 1;
            mlnFormContainerLrn.add(this.__chkbxmulticoreLrn, {row: row, column: 1});
            mlnFormContainerLrn.add(this.__chkbxVerboseLrn, {row: row, column: 2});
            mlnFormContainerLrn.add(this.__chkbxLRemoveFormulas, {row: row, column: 3, colSpan:2});
            row += 1;
            mlnFormContainerLrn.add(this.__btnStartLrn, {row: row, column: 1, colSpan: 4});

            return mlnFormContainerLrn;
        },


        /**
         * send user statistics to server
         */
        _send_user_stats : function() {
            var currentdate = new Date();
            var date = currentdate.getDate() + "/"
                    + (currentdate.getMonth()+1)  + "/"
                    + currentdate.getFullYear();
            var time = currentdate.getHours() + ":"
                    + currentdate.getMinutes() + ":"
                    + currentdate.getSeconds();
        //        var url = 'http://jsonip.appspot.com?callback=?';
            var url = 'https://api.ipify.org?format=jsonp';
            var req = new qx.bom.request.Jsonp();

            var reqServer = new qx.io.request.Xhr();
                reqServer.setUrl("/mln/_user_stats");
                reqServer.setMethod("POST");
                reqServer.setRequestHeader("Cache-Control", "no-cache");
                reqServer.setRequestHeader("Content-Type", "application/json");

            req.onload = function() {
              reqServer.setRequestData({ 'ip': req.responseJson.ip, 'date': date, "time": time });
              reqServer.send();
            }
            req.onerror = function() {
              reqServer.setRequestData({ 'ip': null, 'date': date, "time": time });
              reqServer.send();
            }
            req.open("GET", url);
            req.send();
        },


        /**
         * download currently selected project
         */
        _download_project : function() {
            var project = (this.__tabView.isSelected(this.__inferencePage) ? this.__slctProjectInf : this.__slctProjectLrn).getSelection()[0].getLabel();
            window.open("/mln/projects/" + project,"_self");
        },
        

        /**
        * Update fields when changing the example folder for learning
        */
        _refresh_list : function(field, mln){
            var exampleFolder = (this.__tabView.isSelected(this.__inferencePage) ? this.__slctProjectInf : this.__slctProjectLrn).getSelection()[0].getLabel();
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
        _save_file : function(fname, newname, rename, fcontent) {
            var isInfPage = this.__tabView.isSelected(this.__inferencePage);
            var xmplFldrSlctn = (isInfPage ? this.__slctProjectInf : this.__slctProjectLrn).getSelection()[0].getLabel();

            var req = new qx.io.request.Xhr("/mln/save_edited_file", "POST");
            req.setRequestHeader("Content-Type", "application/json");
            req.setRequestData({"folder": xmplFldrSlctn, "fname": fname, "newfname": newname, "rename": rename, "content": fcontent});
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
            var exampleFolder = this.__slctProjectInf.getSelection()[0].getLabel();
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
            var exampleFolder = this.__slctProjectLrn.getSelection()[0].getLabel();
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
            var row = this._rowmodelext;
            if (e.getData()) {
                this.__mlnFormContainerInf.add(this.__emlnLabel, {row: row, column: 0});
                this.__mlnFormContainerInf.add(this.__slctEMLN, {row: row, column: 1, colSpan: 4});
                row += 1;
                this._rowemlncontainer = row;
                this.__mlnFormContainerInf.add(this.__emlnAreaContainer, {row: row, column: 1, colSpan: 4});
                this.__mlnFormContainerLayout.setRowHeight(this._rowemlncontainer, 250);
                row += 1;
                this.__mlnFormContainerInf.add(this.__chkbxRenameEditEMLN, {row: row, column: 1});
                row += 1;
                this.__mlnFormContainerInf.add(this.__txtFNameEMLN, {row: row, column: 1, colSpan: 3});
                this.__mlnFormContainerInf.add(this.__btnSaveEMLN, {row: row, column: 4});
                row += 1;

                var req = new qx.io.request.Xhr("/mln/inference/_use_model_ext", "GET");
                req.addListener("success", function(e) {
                    var tar = e.getTarget();
                    var that = this;
                    var response = tar.getResponse();
                    for (var i = 0; i < response.emlnfiles.length; i++) {
                        that.__slctEMLN.add(new qx.ui.form.ListItem(response.emlnfiles[i]));
                    }
                }, this);
                req.send();
            } else {
                this.__mlnFormContainerInf.remove(this.__emlnLabel);
                this.__mlnFormContainerInf.remove(this.__slctEMLN);
                this.__mlnFormContainerInf.remove(this.__emlnAreaContainer);
                this.__mlnFormContainerInf.remove(this.__chkbxRenameEditEMLN);
                this.__mlnFormContainerInf.remove(this.__txtFNameEMLN);
                this.__mlnFormContainerInf.remove(this.__btnSaveEMLN);
                this.__mlnFormContainerLayout.setRowHeight(this._rowemlncontainer, 0);
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

            var stateListenerId = file.addListener("changeState", function(evt) {
                var state = evt.getData();

                if (state == "uploading") {
                    console.log(file.getFilename() + " (Uploading...)");
                } else if (state == "uploaded") {
                    console.log(file.getFilename() + " (Complete)");
                    this.__uploader.setAutoUpload(true);
                    if (this.__tabView.isSelected(this.__inferencePage)) {
                        this._change_example_inf();
                    } else {
                        this._change_example_lrn();
                    }
                } else if (state == "cancelled") {
                    console.log(file.getFilename() + " (Cancelled)");
                }
                // Remove the listeners
                if (state == "uploaded" || state == "cancelled") {
                    file.removeListenerById(stateListenerId);
                }
            }, this);
            this.__uploader.setAutoUpload(true);
        },


        /**
        * Uploads a project file
        */
        _uploadProj : function(evt) {
            var file = evt.getData();
            var fileName = file.getFilename();
            var progressListenerId = file.addListener("changeProgress", function(e) {
                console.log("Upload " + fileName + ": " +
                    e.getData() + " / " + file.getSize() + " - " +
                    Math.round(e.getData() / file.getSize() * 100) + "%");

            this.__slctProjectInf.add(new qx.ui.form.ListItem(fileName));
            this.__slctProjectLrn.add(new qx.ui.form.ListItem(fileName));

            }, this);
            console.log('uploading project', fileName);
            this.__projUploader.setAutoUpload(true);
        },


        /**
        * Start the inference process
        */
        _start_inference : function(e) {
                this._show_wait_animation("Inf", true);
                var that = this;
                this.loadGraph();
                this.loadBarChart("dia");
                var mln = (this.__slctMLN.getSelectables().length != 0) ? this.__slctMLN.getSelection()[0].getLabel() : "";
                var emln = (this.__slctEMLN.getSelectables().length != 0) ? this.__slctEMLN.getSelection()[0].getLabel() : "";
                var db = (this.__slctEvidence.getSelectables().length != 0) ? this.__slctEvidence.getSelection()[0].getLabel() : "";
                var method = (this.__slctMethod.getSelectables().length != 0) ? this.__slctMethod.getSelection()[0].getLabel() : "";
                var logic = (this.__slctLogic.getSelectables().length != 0) ? this.__slctLogic.getSelection()[0].getLabel() : "";
                var grammar = (this.__slctGrammar.getSelectables().length != 0) ? this.__slctGrammar.getSelection()[0].getLabel() : "";
                var mlnText = this.codeMirrormlnArea ? this.codeMirrormlnArea.doc.getValue() : "";
                var emlnText = this.codeMirroremlnArea ? this.codeMirroremlnArea.doc.getValue() : "";
                var dbText = this.codeMirrordbArea ? this.codeMirrordbArea.doc.getValue() : "";
                var timeout = this.__chkbxTimeout.getValue() && this.__chkbxTimeout.getEnabled() ? this.__txtFTimeout.getValue() : null;

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
                                    "timeout": timeout,
                                    "grammar": grammar,
                                    "multicore": this.__chkbxmulticore.getValue(),
                                    "ignore_unknown_preds": this.__chkbxIgnoreUnknown.getValue(),
                                    "verbose": this.__chkbxVerbose.getValue()});
                req.addListener("success", function(e) {
                        var that = this;
                        var tar = e.getTarget();
                        var response = tar.getResponse();
                        this._notify(response.message, 100);
                        this._get_inf_status(timeout);
                }, this);
                req.send();
        },


        /**
        * Request inference status
        */
        _get_inf_status : function(timeout) {

            var req = new qx.io.request.Xhr("/mln/inference/_get_status", "POST");
            req.setRequestHeader("Content-Type", "application/json");
            req.setRequestData({"timeout": timeout});
            req.addListener("success", function(e) {
                var that = this;
                var tar = e.getTarget();
                var response = tar.getResponse();

                var message = response.message;

                if (response.status == true) {
                    this._show_wait_animation("Inf", false);

                    this['_barChartdia'].replaceData(response.resbar);
                    this.__textAreaResultsInf.setValue(response.output);
                    this.__textAreaResultsInf.getContentElement().scrollToY(10000);

                    if (response.graphres.length == 0) {

                        message += " Graph contains 0 links.";
                    }
                    else if (response.graphres.length > 200) {
                        message += "Graph cannot be displayed. Generated MRF contains about " + response.graphres.length + " links, exceeding the maximum number of visualizable links.";
                    } else {
                        this.updateGraph([],response.graphres);
                    }

                    this._imgRatio = response.condprob.ratio;
                    this._condProb.resetSource();
                    if (response.img !== '') {
                      this._condProb.setSource('data:image/png;base64,' + response.condprob.png);
                    }
                } else {
                    this._get_inf_status(timeout);
                }
                this._notify(message, 100);
            }, this);
            req.send();
        },


        /**
        * Start the learning process
        */
        _start_learning : function(e) {
                this.__txtAMLNviz.setValue('');
                this._highlight('mlnResultArea');
                this._show_wait_animation("Lrn", true);
                var that = this;
                this.loadGraph();
                var mln = (this.__slctMLNLrn.getSelectables().length != 0) ? this.__slctMLNLrn.getSelection()[0].getLabel() : "";
                var db = (this.__slctTDataLrn.getSelectables().length != 0) ? this.__slctTDataLrn.getSelection()[0].getLabel() : "";
                var method = (this.__slctMethodLrn.getSelectables().length != 0) ? this.__slctMethodLrn.getSelection()[0].getLabel() : "";
                var logic = (this.__slctLogicLrn.getSelectables().length != 0) ? this.__slctLogicLrn.getSelection()[0].getLabel() : "";
                var grammar = (this.__slctGrammarLrn.getSelectables().length != 0) ? this.__slctGrammarLrn.getSelection()[0].getLabel() : "";
                var mlnText = this.codeMirrormlnAreaLrn ? this.codeMirrormlnAreaLrn.doc.getValue() : "";
                var dbText = this.codeMirrortDataArea ? this.codeMirrortDataArea.doc.getValue() : "";
                var timeout = this.__chkbxTimeoutLrn.getValue() && this.__chkbxTimeoutLrn.getEnabled() ? this.__txtFTimeoutLrn.getValue() : null;

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
                                    "timeout": timeout,
                                    "multicore": this.__chkbxmulticoreLrn.getValue(),
                                    "ignore_unknown_preds": this.__chkbxIgnoreUnknownLrn.getValue(),
                                    "ignore_zero_weight_formulas": this.__chkbxLRemoveFormulas.getValue()
                                    });
                req.addListener("success", function(e) {
                        var tar = e.getTarget();
                        var response = tar.getResponse();
                        this._notify(response.message, 100);
                        this._get_lrn_status(timeout);
                }, this);
                req.send();
        },


        /**
        * Request learning status
        */
        _get_lrn_status : function(timeout) {

            var req = new qx.io.request.Xhr("/mln/learning/_get_status", "POST");
            req.setRequestHeader("Content-Type", "application/json");
            req.setRequestData({"timeout": timeout});
            req.addListener("success", function(e) {
                var that = this;
                var tar = e.getTarget();
                var response = tar.getResponse();

                var message = response.message;

                if (response.status == true) {
                    this._show_wait_animation("Lrn", false);
                    this.__txtAMLNviz.setValue(response.learnedmln);
                    this._highlight('mlnResultArea');
                    this.__txtAResultsLrn.setValue(response.output);
                    this.__txtAResultsLrn.getContentElement().scrollToY(10000);
                    this._refresh_list(this.__slctMLNLrn, true);
                } else {
                    this._get_lrn_status(timeout);
                }
                this._notify(message, 100);
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

                    // set examples for inference and learning
                    for (var i = 0; i < response.examples.length; i++) {
                         this.__slctProjectInf.add(new qx.ui.form.ListItem(response.examples[i]));
                         this.__slctProjectLrn.add(new qx.ui.form.ListItem(response.examples[i]));
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
                this.__txtAMLN.setValue('');
                this._highlight(this.__txtAMLN.getContentElement().getAttribute('id'));
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
                this.__txtAEvidence.setValue('');
                this._highlight(this.__txtAEvidence.getContentElement().getAttribute('id'));
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

                // set selected grammar from config
                this.__slctGrammar.setSelection(this.__listitems[config.grammar] ? [this.__listitems[config.grammar]] : []);
                this.__slctLogic.setSelection(this.__listitems[config.logic] ? [this.__listitems[config.logic]] : []);

                // set config for inference
                this.__chkbxApplyCWOption.setValue(config.cw || false);
                this.__txtFParams.setValue(config.params || '');
                this.__txtFQueries.setValue(config.queries || '');
                this.__chkbxVerbose.setValue(config.verbose || false);
                this.__chkbxmulticore.setValue(config.multicore || false);

            } else {
                // set mln files for learning
                this.__txtAMLNLrn.setValue('');
                this._highlight(this.__txtAMLNLrn.getContentElement().getAttribute('id'));
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
                this.__txtATDataLrn.setValue('');
                this._highlight(this.__txtATDataLrn.getContentElement().getAttribute('id'));
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
                    if (methods[i] == config.method) {
                        var selectedmethoditem = new qx.ui.form.ListItem(methods[i]);
                        this.__slctMethodLrn.add(selectedmethoditem);
                    } else {
                        this.__slctMethodLrn.add(new qx.ui.form.ListItem(methods[i]));
                    }
                }
                this.__slctMethodLrn.setSelection(selectedmethoditem ? [selectedmethoditem] : []);

                // set selected grammar from config
                this.__slctGrammarLrn.setSelection(this.__listitemsLrn[config.grammar] ? [this.__listitemsLrn[config.grammar]] : []);
                this.__slctLogicLrn.setSelection(this.__listitemsLrn[config.logic] ? [this.__listitemsLrn[config.logic]] : []);

                // set config for learning
                this.__txtFParamsLrn.setValue(config.params || '');
                this.__chkbxVerboseLrn.setValue(config.verbose || false);
                this.__chkbxmulticoreLrn.setValue(config.cw || false);
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
          this._graph.showLabels(this.__chkbxShowLabels.getValue());
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
            if (e.getData().length > 0) {
                var selection = e.getData()[0].getLabel();
                this._update_text(selection, this.__txtAEMLN);
            } else {
                this.__txtAEMLN.setValue('');
            }
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
            var project = (this.__tabView.isSelected(this.__inferencePage) ? this.__slctProjectInf : this.__slctProjectLrn).getSelection()[0].getLabel();
            var req = new qx.io.request.Xhr();
            req.setUrl("/mln/_get_filecontent");
            req.setMethod('POST');
            req.setRequestHeader("Cache-Control", "no-cache");
            req.setRequestHeader("Content-Type", 'application/json');
            req.setRequestData({ "project": project , "filename": selection });
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
