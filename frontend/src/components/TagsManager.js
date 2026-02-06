import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API } from '../App';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { X, Plus } from 'lucide-react';
import { toast } from 'sonner';

const SUGGESTED_TAGS = [
  'Prioritario', 'Seguimiento', 'Interesado', 'Negociando',
  'Primera visita', 'Segunda visita', 'Documentación pendiente',
  'Crédito aprobado', 'VIP', 'Referido', 'Zona Norte', 'Zona Sur'
];

export default function TagsManager({ leadPhone, initialTags = [], onTagsChange }) {
  const [tags, setTags] = useState(initialTags);
  const [newTag, setNewTag] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [allTags, setAllTags] = useState([]);

  useEffect(() => {
    fetchAllTags();
  }, []);

  useEffect(() => {
    setTags(initialTags);
  }, [initialTags]);

  const fetchAllTags = async () => {
    try {
      const response = await axios.get(`${API}/tags`);
      setAllTags(response.data.map(t => t.tag));
    } catch (error) {
      console.error('Error fetching tags:', error);
    }
  };

  const addTag = async (tag) => {
    const trimmedTag = tag.trim();
    if (!trimmedTag || tags.includes(trimmedTag)) return;

    try {
      await axios.post(`${API}/leads/${leadPhone}/tags`, { tag: trimmedTag });
      const updatedTags = [...tags, trimmedTag];
      setTags(updatedTags);
      setNewTag('');
      setShowSuggestions(false);
      if (onTagsChange) onTagsChange(updatedTags);
      toast.success(`Tag "${trimmedTag}" agregado`);
    } catch (error) {
      toast.error('Error al agregar tag');
    }
  };

  const removeTag = async (tag) => {
    try {
      await axios.delete(`${API}/leads/${leadPhone}/tags/${encodeURIComponent(tag)}`);
      const updatedTags = tags.filter(t => t !== tag);
      setTags(updatedTags);
      if (onTagsChange) onTagsChange(updatedTags);
      toast.success(`Tag "${tag}" eliminado`);
    } catch (error) {
      toast.error('Error al eliminar tag');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && newTag.trim()) {
      e.preventDefault();
      addTag(newTag);
    }
  };

  // Combinar tags sugeridos con los más usados
  const suggestions = [...new Set([...SUGGESTED_TAGS, ...allTags])]
    .filter(t => !tags.includes(t))
    .filter(t => t.toLowerCase().includes(newTag.toLowerCase()))
    .slice(0, 8);

  return (
    <div className="tags-manager" data-testid="tags-manager">
      <div className="tags-list">
        {tags.map((tag) => (
          <Badge key={tag} variant="secondary" className="tag-badge">
            {tag}
            <button 
              className="tag-remove"
              onClick={() => removeTag(tag)}
              data-testid={`remove-tag-${tag}`}
            >
              <X className="h-3 w-3" />
            </button>
          </Badge>
        ))}
      </div>

      <div className="tags-input-container">
        <div className="tags-input-wrapper">
          <Input
            type="text"
            placeholder="Agregar tag..."
            value={newTag}
            onChange={(e) => {
              setNewTag(e.target.value);
              setShowSuggestions(true);
            }}
            onKeyDown={handleKeyDown}
            onFocus={() => setShowSuggestions(true)}
            className="tags-input"
            data-testid="tag-input"
          />
          <Button 
            size="sm" 
            onClick={() => addTag(newTag)}
            disabled={!newTag.trim()}
            data-testid="btn-add-tag"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>

        {showSuggestions && suggestions.length > 0 && (
          <div className="tags-suggestions" data-testid="tag-suggestions">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                className="tag-suggestion"
                onClick={() => addTag(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
