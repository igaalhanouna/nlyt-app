import React from 'react';

export default function InvitationCardHeader({ organizer, responseStatus, statusBadge }) {
  return (
    <div className={`px-6 py-4 ${
      responseStatus === 'accepted' || responseStatus === 'accepted_guaranteed' ? 'bg-green-500' :
      responseStatus === 'accepted_pending_guarantee' ? 'bg-amber-500' :
      responseStatus === 'declined' ? 'bg-red-500' :
      responseStatus === 'cancelled_by_participant' ? 'bg-orange-500' :
      'bg-slate-800'
    } text-white`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm opacity-90">Invitation de</p>
          <p className="text-xl font-semibold">{organizer.name}</p>
        </div>
        {statusBadge}
      </div>
    </div>
  );
}
