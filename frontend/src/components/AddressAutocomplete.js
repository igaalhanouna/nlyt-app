import React, { useState, useEffect, useRef, useCallback } from 'react';
import { MapPin, Loader2, X } from 'lucide-react';

/**
 * AddressAutocomplete component using French Government BAN API
 * (Base Adresse Nationale) - Free, no API key required
 * 
 * Features:
 * - Real-time address suggestions
 * - Debounced search (300ms)
 * - Returns address, latitude, longitude
 * - Keyboard navigation support
 * - Clean UX with loading states
 */
const AddressAutocomplete = ({ 
  value, 
  onChange, 
  onSelect,
  placeholder = "Tapez une adresse...",
  className = "",
  disabled = false
}) => {
  const [inputValue, setInputValue] = useState(value || '');
  const [suggestions, setSuggestions] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [noResults, setNoResults] = useState(false);
  
  const inputRef = useRef(null);
  const suggestionsRef = useRef(null);
  const debounceRef = useRef(null);

  // Sync external value changes
  useEffect(() => {
    if (value !== undefined && value !== inputValue) {
      setInputValue(value);
    }
  }, [value]);

  // Debounced search function
  const searchAddresses = useCallback(async (query) => {
    if (!query || query.length < 3) {
      setSuggestions([]);
      setNoResults(false);
      return;
    }

    setIsLoading(true);
    setNoResults(false);

    try {
      // Using BAN API (Base Adresse Nationale) - French government free API
      const response = await fetch(
        `https://api-adresse.data.gouv.fr/search/?q=${encodeURIComponent(query)}&limit=5&autocomplete=1`
      );
      
      if (!response.ok) throw new Error('API error');
      
      const text = await response.text();
      let data;
      try { data = JSON.parse(text); } catch { data = {}; }
      
      if (data.features && data.features.length > 0) {
        const formattedSuggestions = data.features.map((feature) => ({
          id: feature.properties.id,
          label: feature.properties.label,
          name: feature.properties.name,
          city: feature.properties.city,
          postcode: feature.properties.postcode,
          context: feature.properties.context,
          latitude: feature.geometry.coordinates[1],
          longitude: feature.geometry.coordinates[0],
          type: feature.properties.type // housenumber, street, municipality
        }));
        setSuggestions(formattedSuggestions);
        setNoResults(false);
      } else {
        setSuggestions([]);
        setNoResults(true);
      }
    } catch (error) {
      console.error('Address search error:', error);
      setSuggestions([]);
      setNoResults(true);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Handle input change with debounce
  const handleInputChange = (e) => {
    const newValue = e.target.value;
    setInputValue(newValue);
    setShowSuggestions(true);
    setHighlightedIndex(-1);
    
    // Notify parent of text change
    if (onChange) {
      onChange(newValue);
    }

    // Clear previous timeout
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    // Debounce API call (300ms)
    debounceRef.current = setTimeout(() => {
      searchAddresses(newValue);
    }, 300);
  };

  // Handle suggestion selection
  const handleSelectSuggestion = (suggestion) => {
    setInputValue(suggestion.label);
    setSuggestions([]);
    setShowSuggestions(false);
    setNoResults(false);
    
    // Notify parent with full address data
    if (onSelect) {
      onSelect({
        address: suggestion.label,
        latitude: suggestion.latitude,
        longitude: suggestion.longitude,
        place_id: suggestion.id,
        city: suggestion.city,
        postcode: suggestion.postcode
      });
    }
    
    // Also update the simple onChange
    if (onChange) {
      onChange(suggestion.label);
    }
  };

  // Keyboard navigation
  const handleKeyDown = (e) => {
    if (!showSuggestions || suggestions.length === 0) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setHighlightedIndex((prev) => 
          prev < suggestions.length - 1 ? prev + 1 : prev
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : -1));
        break;
      case 'Enter':
        e.preventDefault();
        if (highlightedIndex >= 0 && highlightedIndex < suggestions.length) {
          handleSelectSuggestion(suggestions[highlightedIndex]);
        }
        break;
      case 'Escape':
        setShowSuggestions(false);
        setHighlightedIndex(-1);
        break;
      default:
        break;
    }
  };

  // Close suggestions when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        inputRef.current && 
        !inputRef.current.contains(event.target) &&
        suggestionsRef.current &&
        !suggestionsRef.current.contains(event.target)
      ) {
        setShowSuggestions(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);

  const clearInput = () => {
    setInputValue('');
    setSuggestions([]);
    setShowSuggestions(false);
    setNoResults(false);
    if (onChange) onChange('');
    inputRef.current?.focus();
  };

  return (
    <div className="relative w-full">
      <div className="relative">
        <MapPin className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={() => inputValue.length >= 3 && setShowSuggestions(true)}
          placeholder={placeholder}
          disabled={disabled}
          className={`w-full pl-10 pr-10 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-slate-900 focus:border-transparent disabled:bg-slate-100 disabled:cursor-not-allowed ${className}`}
          data-testid="address-autocomplete-input"
          autoComplete="off"
        />
        
        {/* Loading indicator or clear button */}
        <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
          {isLoading ? (
            <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />
          ) : inputValue && (
            <button
              type="button"
              onClick={clearInput}
              className="text-slate-400 hover:text-slate-600"
              data-testid="address-clear-btn"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Suggestions dropdown */}
      {showSuggestions && (suggestions.length > 0 || noResults) && (
        <div
          ref={suggestionsRef}
          className="absolute z-50 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-60 overflow-y-auto"
          data-testid="address-suggestions-dropdown"
        >
          {noResults ? (
            <div className="px-4 py-3 text-sm text-slate-500 text-center">
              Aucune adresse trouvée
            </div>
          ) : (
            suggestions.map((suggestion, index) => (
              <button
                key={suggestion.id}
                type="button"
                onClick={() => handleSelectSuggestion(suggestion)}
                onMouseEnter={() => setHighlightedIndex(index)}
                className={`w-full px-4 py-3 text-left hover:bg-slate-50 transition-colors flex items-start gap-3 ${
                  index === highlightedIndex ? 'bg-slate-100' : ''
                } ${index !== suggestions.length - 1 ? 'border-b border-slate-100' : ''}`}
                data-testid={`address-suggestion-${index}`}
              >
                <MapPin className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-900 truncate">
                    {suggestion.name}
                  </p>
                  <p className="text-xs text-slate-500 truncate">
                    {suggestion.postcode} {suggestion.city}
                  </p>
                </div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default AddressAutocomplete;
