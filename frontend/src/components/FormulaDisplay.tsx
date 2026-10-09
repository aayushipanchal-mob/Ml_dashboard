import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Calculator } from 'lucide-react';
import type { Formula } from '../api/types';

interface FormulaDisplayProps {
  formula?: Formula;
}

export const FormulaDisplay: React.FC<FormulaDisplayProps> = ({ formula }) => {
  const [isOpen, setIsOpen] = useState(false);

  if (!formula) return null;

  return (
    <div style={{ position: 'relative' }}>
      <button 
        className="formula-toggle" 
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <Calculator size={16} />
        {isOpen ? 'Hide Formula' : 'Show Formula'}
        {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>

      {isOpen && (
        <div className="formula-content">
          <div style={{ marginBottom: '8px', color: 'var(--accent-blue)' }}>
            <strong>{formula.name}</strong>
          </div>
          <div>Expression: <code>{formula.expression}</code></div>
          
          <div className="formula-math">
            <div className="fraction">
              <div className="numerator">
                {formula.numerator_value !== undefined ? (
                  <span title={formula.numerator}>{formula.numerator_value.toLocaleString()}</span>
                ) : (
                  formula.numerator
                )}
              </div>
              <div className="denominator">
                {formula.denominator_value !== undefined ? (
                  <span title={formula.denominator}>{formula.denominator_value.toLocaleString()}</span>
                ) : (
                  formula.denominator
                )}
              </div>
            </div>
            <div>
              {formula.numerator_value !== undefined && formula.denominator_value !== undefined && (
                <span> = {((formula.numerator_value / (formula.denominator_value || 1)) * 100).toFixed(2)}%</span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
