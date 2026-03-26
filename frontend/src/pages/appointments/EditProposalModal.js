import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../../components/ui/dialog';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { FileEdit, Send, Loader2 } from 'lucide-react';

export default function EditProposalModal({
  open, onClose,
  proposalForm, setProposalForm,
  submittingProposal, onSubmitProposal,
}) {
  const isPastDate = proposalForm.start_datetime && new Date(proposalForm.start_datetime) <= new Date();

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="sm:max-w-[540px]" data-testid="edit-proposal-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileEdit className="w-5 h-5 text-blue-600" />
            Proposer une modification
          </DialogTitle>
          <DialogDescription>
            Les participants devront accepter cette modification avant qu'elle ne soit appliquée.
          </DialogDescription>
        </DialogHeader>

        <div className="grid sm:grid-cols-2 gap-4 mt-2">
          <div>
            <Label htmlFor="prop-datetime">Date et heure</Label>
            <Input
              id="prop-datetime" type="datetime-local" data-testid="proposal-datetime-input"
              value={proposalForm.start_datetime}
              min={(() => { const n = new Date(); return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}-${String(n.getDate()).padStart(2, '0')}T${String(n.getHours()).padStart(2, '0')}:${String(n.getMinutes()).padStart(2, '0')}`; })()}
              onChange={(e) => setProposalForm({ ...proposalForm, start_datetime: e.target.value })}
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="prop-duration">Durée (minutes)</Label>
            <Input
              id="prop-duration" type="number" min="15" step="15" data-testid="proposal-duration-input"
              value={proposalForm.duration_minutes}
              onChange={(e) => setProposalForm({ ...proposalForm, duration_minutes: e.target.value })}
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="prop-type">Type</Label>
            <select
              id="prop-type" data-testid="proposal-type-select"
              value={proposalForm.appointment_type}
              onChange={(e) => setProposalForm({ ...proposalForm, appointment_type: e.target.value })}
              className="mt-1 w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="physical">En personne</option>
              <option value="video">Visioconférence</option>
            </select>
          </div>
          <div>
            <Label htmlFor="prop-location">{proposalForm.appointment_type === 'video' ? 'Plateforme visio' : 'Lieu'}</Label>
            {proposalForm.appointment_type === 'video' ? (
              <select
                id="prop-location" data-testid="proposal-provider-select"
                value={proposalForm.meeting_provider || ''}
                onChange={(e) => setProposalForm({ ...proposalForm, meeting_provider: e.target.value })}
                className="mt-1 w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="">-- Sélectionner --</option>
                <option value="zoom">Zoom</option>
                <option value="teams">Microsoft Teams</option>
                <option value="meet">Google Meet</option>
                <option value="external">Lien externe</option>
              </select>
            ) : (
              <Input
                id="prop-location" data-testid="proposal-location-input"
                value={proposalForm.location}
                onChange={(e) => setProposalForm({ ...proposalForm, location: e.target.value })}
                className="mt-1"
              />
            )}
          </div>
        </div>

        {isPastDate && (
          <p className="text-sm text-red-600 mt-1" data-testid="proposal-datetime-past-error">
            La date et l'heure de l'engagement doivent être dans le futur
          </p>
        )}

        <div className="flex gap-2 mt-4 justify-end">
          <Button variant="outline" onClick={onClose} data-testid="cancel-proposal-form-btn">
            Annuler
          </Button>
          <Button onClick={onSubmitProposal} disabled={submittingProposal} data-testid="submit-proposal-btn">
            {submittingProposal ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Send className="w-4 h-4 mr-1" />}
            Envoyer la proposition
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
