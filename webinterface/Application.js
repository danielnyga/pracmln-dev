/* ************************************************************************

   Copyright:

   License:

   Authors:

************************************************************************ */

/**
 * This is the main application class of your custom application "myapp"
 *
 * @asset(myapp/*)
 */
qx.Class.define("myapp.Application",
{
	extend : qx.application.Standalone,



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
    	main : function()
    	{
      	// Call super class
      	this.base(arguments);

      	var decorator = new qx.ui.decoration.Decorator().set({
        	width: 10,
        	color: "#ddd"
	      });
	      //this.__desktop = new qx.ui.window.Desktop().set({
	      //  decorator: decorator
	      //});
	      //this.add(this.__desktop, {edge: 0, top: 0});
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

	var root = qx.core.Init.getApplication().getRoot();
	var windowManager = new qx.ui.window.Manager();
	var desktop = new qx.ui.window.Desktop(windowManager);
	root.add(desktop);
	//var widgets = this._widgets;

	var response = null;
	var req = null;

	var win1 = new qx.ui.window.Window("MLN Query Tool", null).set({
		width:100
        });
	var win2 = new qx.ui.window.Window("Graph", null);
	var win3 = new qx.ui.window.Window("Results", null).set({
		width:500,
		height:400
	});
	
	var layout = new qx.ui.layout.Grid();
	var layout3 = new qx.ui.layout.Grow();
        
	layout.setRowFlex(4, 1);
	layout.setRowFlex(12, 1);

	win1.setLayout(layout);
	win1.setShowStatusbar(false);

	win3.setLayout(layout3);
	//win1.setStatus("Demo loaded");

	//win1.addListener("move", function(e){}, this);
	//win1.addListener("resize", function(e){}, this);

	var label1 = new qx.ui.basic.Label("Engine:");
	var label2 = new qx.ui.basic.Label("Grammar:");
	var label3 = new qx.ui.basic.Label("Logic:");
	var label4 = new qx.ui.basic.Label("MLN:");
	var label5 = new qx.ui.basic.Label("Evidence:");
	var label6 = new qx.ui.basic.Label("Method:");
	var label7 = new qx.ui.basic.Label("Queries:");
	var label8 = new qx.ui.basic.Label("Max. steps:");
	var label9 = new qx.ui.basic.Label("Num. chains:");
	var label10 = new qx.ui.basic.Label("Add. params:");
	var label11 = new qx.ui.basic.Label("CW preds:");
	var label12 = new qx.ui.basic.Label("Output:");

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
	var textAreaResults = new qx.ui.form.TextArea("");

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

	buttonStart.addListener("execute",function(e) {
						//req = new qx.io.remote.Request("/_start_inference", "GET", "text/plain");
						req = new qx.io.request.Xhr(); 
						req.setUrl("/_start_inference");
						req.setMethod("GET");
						var mln = (selectMLN.getSelectables().length != 0) ? selectMLN.getSelection()[0].getLabel() : "";
						var emln = (selectEMLN.getSelectables().length != 0) ? selectEMLN.getSelection()[0].getLabel() : "";
						var db = (selectEvidence.getSelectables().length != 0) ? selectEvidence.getSelection()[0].getLabel() : "";
						var method = (selectMethod.getSelectables().length != 0) ? selectMethod.getSelection()[0].getLabel() : "";
						var engine = (selectEngine.getSelectables().length != 0) ? selectEngine.getSelection()[0].getLabel() : "";
						var logic = (selectLogic.getSelectables().length != 0) ? selectLogic.getSelection()[0].getLabel() : "";
						var grammar = (selectGrammar.getSelectables().length != 0) ? selectGrammar.getSelection()[0].getLabel() : "";  
						/*setRequestData						
						req.setParameter("mln", mln);
						req.setParameter("emln", emln);
						req.setParameter("db", db);
						req.setParameter("method", method);
						req.setParameter("engine", engine);
						req.setParameter("logic", logic);
						req.setParameter("grammar", grammar);
						req.setParameter("mln_text", textAreaMLN.getValue());
						req.setParameter("db_text", textAreaEvidence.getValue());
						req.setParameter("output", textFieldOutput.getValue());
						req.setParameter("params", textFieldAddParams.getValue());
						req.setParameter("mln_rename_on_edit", checkBoxRenameEditMLN.getValue());
						req.setParameter("db_rename_on_edit", checkBoxRenameEditEvidence.getValue());
						req.setParameter("query", textFieldQueries.getValue());
						req.setParameter("closed_world", checkBoxApplyCWOption.getValue());
						req.setParameter("cw_preds", textFieldCWPreds.getValue());
						req.setParameter("convert_to_alchemy", checkBoxConvertAlchemy.getValue());
						req.setParameter("use_emln", checkBoxUseModelExt.getValue());
						req.setParameter("max_steps", textFieldMaxSteps.getValue());
						req.setParameter("num_chains", textFieldNumChains.getValue());
						req.setParameter("use_multicpu", checkBoxUseAllCPU.getValue());*/
						req.setRequestData({"mln":mln,"emln":emln,"db":db,"method":method,"engine":engine,"logic":logic,"grammar":grammar,"mln_text":textAreaMLN.getValue(),"db_text":textAreaEvidence.getValue(),"output":textFieldOutput.getValue(),"params":textFieldAddParams.getValue(),"mln_rename_on_edit":checkBoxRenameEditMLN.getValue(),"db_rename_on_edit":checkBoxRenameEditEvidence.getValue(),"query":textFieldQueries.getValue(),"closed_world":checkBoxApplyCWOption.getValue(),"cw_preds":textFieldCWPreds.getValue(),"convert_to_alchemy":checkBoxConvertAlchemy.getValue(),"use_emln":checkBoxUseModelExt.getValue(),"max_steps":textFieldMaxSteps.getValue(),"num_chains":textFieldNumChains.getValue(),"use_multicpu":checkBoxUseAllCPU.getValue()});
						req.addListener("success", function(e) {
								var tar = e.getTarget();								
								//response = e.getContent();
								response = tar.getResponse();
								textAreaResults.setValue(response);
								win1.open();
								desktop.setActiveWindow(win3);
									
						});
						win1.close();
						desktop.setActiveWindow(win3);
						win3.open();
						req.send();
						
	});
	buttonSaveMLN.addListener("execute",function(e){
						req = new qx.io.remote.Request("/_test", "GET", "text/plain");
						req.addListener("completed", function(e) {
								alert(e.getContent());
						});
						req.send();

	});
	buttonSaveEMLN.addListener("execute",function(e){});
	buttonSaveEvidence.addListener("execute",function(e){});

	checkBoxRenameEditMLN.addListener("changeValue",function(e){});
	checkBoxRenameEditEvidence.addListener("changeValue",function(e){});
	checkBoxRenameEditEMLN.addListener("changeValue",function(e){});
	checkBoxConvertAlchemy.addListener("changeValue",function(e){});
	checkBoxUseModelExt.addListener("changeValue",function(e) {
								if (Boolean(checkBoxUseModelExt.getValue())) {
									win1.add(selectEMLN, {row: 7, column: 1, colSpan: 2});
									win1.add(buttonSaveEMLN, {row: 7, column: 3});
									win1.add(textAreaEMLN, {row: 8, column: 1, colSpan: 3});
									win1.add(checkBoxRenameEditEMLN, {row: 9, column: 1});
									win1.add(textFieldNameEMLN, {row: 10, column: 1, colSpan: 3});
									layout.setRowFlex(8, 1);
									req = new qx.io.remote.Request("/_use_model_ext", "GET", "text/plain");
									req.addListener("completed", function(e) {
										response = e.getContent().split(",");
										for (var i = 0; i < response.length; i++) {
											selectEMLN.add(new qx.ui.form.ListItem(response[i]));
										}
									});
									req.send();
								} else {
									win1.remove(selectEMLN);
									win1.remove(buttonSaveEMLN);
									win1.remove(textAreaEMLN);
									win1.remove(checkBoxRenameEditEMLN);
									win1.remove(textFieldNameEMLN);
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
								req = new qx.io.remote.Request("/_change_engine", "GET", "text/plain");
								req.setParameter("engine", item.getLabel());
								req.addListener("completed", function(e) {
									response = e.getContent().split(";");
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
								req = new qx.io.remote.Request("/_mln", "GET", "text/plain");
								req.setParameter("filename", item.getLabel());
								req.addListener("completed", function(e) {
									response = e.getContent();
									textAreaMLN.setValue(response);
								
								});
								req.send();	
								
								
	});
	selectEMLN.addListener("changeSelection",function(e){});	
	selectEvidence.addListener("changeSelection",function(e){
								var item = selectEvidence.getSelection()[0];
								textFieldDB.setValue(item.getLabel());
								req = new qx.io.remote.Request("/_load_evidence", "GET", "text/plain");	
								req.setParameter("filename", item.getLabel());
								req.addListener("completed", function(e) {
									response = e.getContent().split(";");
									textAreaEvidence.setValue(response[0]);
									textFieldQueries.setValue(response[1]);
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
	
	win1.add(label1, {row: 0, column: 0});
	win1.add(label2, {row: 1, column: 0});
	win1.add(label3, {row: 2, column: 0});
	win1.add(label4, {row: 3, column: 0});
	win1.add(label5, {row: 11, column: 0});
	win1.add(label6, {row: 15, column: 0});
	win1.add(label7, {row: 16, column: 0});
	win1.add(label8, {row: 17, column: 0});
	win1.add(label9, {row: 18, column: 0});
	win1.add(label10, {row: 19, column: 0});
	win1.add(label11, {row: 20, column: 0});
	win1.add(label12, {row: 21, column: 0});

	win1.add(selectEngine, {row: 0, column: 1, colSpan: 3});
	win1.add(selectGrammar, {row: 1, column: 1, colSpan: 3});
	win1.add(selectLogic, {row: 2, column: 1, colSpan: 3});
	win1.add(selectMLN, {row: 3, column: 1, colSpan: 2});
	//win1.add(selectEMLN, {row: 7, column: 1});
	win1.add(selectEvidence, {row: 11, column: 1, colSpan: 2});
	win1.add(selectMethod, {row: 15, column: 1, colSpan: 3});

	win1.add(buttonStart, {row: 22, column: 1, colSpan: 3});
	win1.add(buttonSaveMLN, {row: 3, column: 3});
	win1.add(buttonSaveEvidence, {row: 11, column: 3});
	//win1.add(buttonSaveEMLN, {row: 15, column: 2});

	win1.add(textAreaMLN, {row: 4, column: 1, colSpan: 3});
	//win1.add(textAreaEMLN, {row: 8, column: 1});
	win1.add(textAreaEvidence, {row: 12, column: 1, colSpan: 3});

	win1.add(textFieldNameMLN, {row: 6, column: 1, colSpan: 3});
	//win1.add(textFieldNameEMLN, {row: 10, column: 1});
	win1.add(textFieldDB, {row: 14, column: 1, colSpan: 3});
	win1.add(textFieldQueries, {row: 16, column: 1, colSpan: 3});
	win1.add(textFieldMaxSteps, {row: 17, column: 1, colSpan: 3});
	win1.add(textFieldNumChains, {row: 18, column: 1, colSpan: 3});
	win1.add(textFieldAddParams, {row: 19, column: 1, colSpan: 3});
	win1.add(textFieldCWPreds, {row: 20, column: 1});
	win1.add(textFieldOutput, {row: 21, column: 1, colSpan: 2});

	win1.add(checkBoxRenameEditMLN, {row: 5, column: 1});
	win1.add(checkBoxConvertAlchemy, {row: 5, column: 2});
	win1.add(checkBoxUseModelExt, {row: 5, column: 3});
	//win1.add(checkBoxRenameEditEMLN, {row: 9, column: 1});
	win1.add(checkBoxRenameEditEvidence, {row: 13, column: 1});
	win1.add(checkBoxApplyCWOption, {row: 20, column: 2});
	win1.add(checkBoxUseAllCPU, {row: 20, column: 3});
	win1.add(checkBoxSaveOutput, {row: 21, column: 3});

	win3.add(textAreaResults);
	      
	desktop.add(win1, {left: 0, top: 0});
	desktop.add(win3, {left: 150, top: 150});

	textFieldOutput.setValue("smoking-test-smoking.results");
	//Fetch options to choose from
	req = new qx.io.remote.Request("/_init", "GET", "text/plain");
	req.addListener("completed", function(e) {
						response = e.getContent().split(";");
						var sub;
						for (var i = 0; i < response.length; i++) {
							if (i == 3) {
								sub = response[i].split(",,");
							} else if (i == 4) {
								textFieldQueries.setValue(response[i]);
								continue;
							} else if (i == 5) {
								textFieldMaxSteps.setValue(response[i]);
								continue;
							} else {
								sub = response[i].split(",");
							}
							for (var j = 0; j < sub.length; j++) {
								switch(i) {
									case 0: selectEngine.add(new qx.ui.form.ListItem(sub[j]));
										break;
									case 1: selectMethod.add(new qx.ui.form.ListItem(sub[j]));
										break;
									case 2: selectMLN.add(new qx.ui.form.ListItem(sub[j]));
										break;
									case 3: selectEvidence.add(new qx.ui.form.ListItem(sub[j]));
										break;
									default:
								}
								
							}
						}
	});
	req.send();
	win1.open();
	}
	
    }
   
});
