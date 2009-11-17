/*
 * Created on Nov 16, 2009
 *
 * TODO To change the template for this generated file go to
 * Window - Preferences - Java - Code Style - Code Templates
 */
package edu.tum.cs.inference;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.io.Serializable;
import java.util.HashMap;

/**
 * generally usable representation of a distribution that can be written to a file.
 * Any BasicSampledDistribution can be converted to this type of object.
 * @author jain
 */
public class GeneralSampledDistribution extends BasicSampledDistribution implements Serializable {

	private static final long serialVersionUID = 1L;
	protected String[] varNames;
	protected String[][] domains;
	protected HashMap<String,Integer> varName2Index;
	
	
	public GeneralSampledDistribution(double[][] values, Double Z, String[] varNames, String[][] domains) {
		this.values = values;
		this.Z = Z;
		this.varNames = varNames;
		this.domains = domains;
		varName2Index = new HashMap<String,Integer>();
		for(int i = 0; i < varNames.length; i++)
			varName2Index.put(varNames[i], i);
	}
	
	@Override
	public String[] getDomain(int idx) {
		return domains[idx];
	}

	@Override
	public String getVariableName(int idx) {
		return varNames[idx];
	}

	/**
	 * writes this object to a file
	 * @param f
	 * @throws IOException
	 */
	public void write(File f) throws IOException {
		FileOutputStream fos = new FileOutputStream(f);
		ObjectOutputStream oos = new ObjectOutputStream(fos);
		oos.writeObject(this);
		oos.close();
	}
	
	/**
	 * reads a previously stored distribution from a file
	 * @param s
	 * @return
	 * @throws IOException
	 * @throws ClassNotFoundException
	 */
	public static GeneralSampledDistribution fromFile(File f) throws IOException, ClassNotFoundException {
		java.io.ObjectInputStream objstream = new ObjectInputStream(new FileInputStream(f));
	    java.lang.Object object = objstream.readObject();
	    objstream.close();
	    return (GeneralSampledDistribution)object;
	}

	@Override
	public int getVariableIndex(String name) {		
		return varName2Index.get(name);
	}
}