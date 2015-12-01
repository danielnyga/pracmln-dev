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
	/*
	function createCORSRequest(method, url){
	    var xhr = new XMLHttpRequest();
	    	if ("withCredentials" in xhr){
			xhr.open(method, url, true);
	    	} else if (typeof XDomainRequest != "undefined"){
			xhr = new XDomainRequest();
			xhr.open(method, url);
	    	} else {
			xhr = null;
	    	}
	    	return xhr;
	}*/

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

	//__desktop: null;
	//var widgets = this._widgets;

	//var req = new qx.io.remote.Request("127.0.0.1:5000/_add_numbers", "GET", "text/plain");

	

	//var req = createCORSRequest("get", "http://www.stackoverflow.com/");
	//if (req){
    	//	req.addListener("completed", function(e) {
  		//alert(e.getContent());
	//});
    	//};
    	//req.onreadystatechange = handler;
    	//req.send();
	//}

	//var url = "0.0.0.0:8080"
	var response = null;

	var win1 = new qx.ui.window.Window("MLN Query Tool", null).set({
		width:100,
        	allowShrinkX: false,
        	allowShrinkY: false,
        	allowGrowX: false
        });
	var win2 = new qx.ui.window.Window("Graph", null);
	
	var layout = new qx.ui.layout.Grid();
        
	layout.setRowFlex(0, 1); // make row 0 flexible
	layout.setColumnWidth(1, 100); // set with of column 1 to 200 pixel

	//win.setLayout(new qx.ui.layout.VBox(10));
	win1.setLayout(layout);
	win1.setShowStatusbar(false);
	win1.setStatus("Demo loaded");

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
						//var req = new qx.io.remote.Request("/run", "POST", "text/plain");
						//req.setData("foobar");
						//req.send();
						
					  });
	buttonSaveMLN.addListener("execute",function(e){});
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
								} else {
									win1.remove(selectEMLN);
									win1.remove(buttonSaveEMLN);
									win1.remove(textAreaEMLN);
									win1.remove(checkBoxRenameEditEMLN);
									win1.remove(textFieldNameEMLN);
								}
							});
	checkBoxApplyCWOption.addListener("changeValue",function(e){});
	checkBoxUseAllCPU.addListener("changeValue",function(e){});
	checkBoxSaveOutput.addListener("changeValue",function(e){});
		
	selectEngine.addListener("changeSelection",function(e) {
								var item = selectEngine.getSelection()[0];
								switch (item.getLabel()) {
									case "PRACMLNs":
										if (response != null) {
											selectMethod.removeAll();
											var sub = response[1].split(",");
											for (var j = 0; j < sub.length; j++) {
												selectMethod.add(new qx.ui.form.ListItem(sub[j]));
											}
										}
										
										checkBoxApplyCWOption.setEnabled(false);
										break;
									case "J-MLNs":
										selectMethod.removeAll();
										selectMethod.add(new qx.ui.form.ListItem("MaxWalkSAT (MPE)"));
										selectMethod.add(new qx.ui.form.ListItem("MC-SAT"));
										selectMethod.add(new qx.ui.form.ListItem("Toulbar2 B&B (MPE)"));
										checkBoxApplyCWOption.setEnabled(false);
										break;
									default:
										selectMethod.removeAll();
										selectMethod.add(new qx.ui.form.ListItem("MC-SAT"));
										selectMethod.add(new qx.ui.form.ListItem("Gibbs sampling"));
										selectMethod.add(new qx.ui.form.ListItem("simulated tempering"));
										selectMethod.add(new qx.ui.form.ListItem("MaxWalkSAT (MPE)"));
										selectMethod.add(new qx.ui.form.ListItem("belief propagation"))
										checkBoxApplyCWOption.setEnabled(true);
								}				
						});
	selectGrammar.addListener("changeSelection",function(e){});
	selectLogic.addListener("changeSelection",function(e){});
	selectMLN.addListener("changeSelection",function(e){
								var item = selectMLN.getSelection()[0];
								var req = new qx.io.remote.Request("/_mln", "GET", "text/plain");
								req.setParameter('filename',item.getLabel());
								req.addListener("completed", function(e) {
									response = e.getContent();
									textAreaMLN.setValue(response);
								
								});
								req.send();	
								
								
						});
	selectEMLN.addListener("changeSelection",function(e){});	
	selectEvidence.addListener("changeSelection",function(e){});
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
	      
	//this.__desktop.add(win, {left: 0, top: 0});
	//select.addListener("changeSelection",function(e){});
	//select.add(new qx.ui.form.ListItem("Item 1"));

	// Document is the application root
	//var doc = this.getRoot();
	// Add button to document at fixed coordinates
	//doc.add(button1, {left: 100, top: 50});
	//win.add(container);
	
	selectMLN.add(new qx.ui.form.ListItem('wts.pybpll.smoking-train-smoking.mln'));
	var req = new qx.io.remote.Request("/_options", "GET", "text/plain");
	req.addListener("completed", function(e) {
						response = e.getContent().split(";");
						var sub;
						for (var i = 0; i < response.length; i++) {
							sub = response[i].split(",");
							for (var j = 0; j < sub.length; j++) {
								switch(i) {
									case 0: selectEngine.add(new qx.ui.form.ListItem(sub[j]));
										break;
									case 1: selectMethod.add(new qx.ui.form.ListItem(sub[j]));
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
