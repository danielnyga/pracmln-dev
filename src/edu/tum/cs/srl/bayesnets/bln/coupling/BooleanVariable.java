/*
 * Created on Oct 27, 2009
 *
 * TODO To change the template for this generated file go to
 * Window - Preferences - Java - Code Style - Code Templates
 */
package edu.tum.cs.srl.bayesnets.bln.coupling;

import edu.tum.cs.logic.GroundAtom;
import edu.tum.cs.logic.GroundLiteral;
import edu.tum.cs.logic.PossibleWorld;
import edu.tum.cs.logic.WorldVariables;
import edu.tum.cs.util.datastruct.ArraySlice;

public class BooleanVariable implements IVariableLogicCoupler {
	protected GroundAtom ga;
	
	public BooleanVariable(GroundAtom ga) {
		this.ga = ga;
	}
	
	public int getValue(PossibleWorld w) {			
		return w.get(ga.index) ? 0 : 1; // True is first element
	}
	
	public void setValue(PossibleWorld w, int domIdx) {
		w.set(ga.index, domIdx == 0);
	}

	public GroundLiteral getGroundLiteral(int domIdx, WorldVariables worldVars) {
		return new GroundLiteral(domIdx == 0, ga);
	}
	
	public Iterable<String> getOriginalParams() {
		return new ArraySlice<String>(ga.args, 0);
	}
}