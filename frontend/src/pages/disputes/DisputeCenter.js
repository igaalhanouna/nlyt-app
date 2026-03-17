import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { ArrowLeft } from 'lucide-react';

export default function DisputeCenter() {
  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-6xl mx-auto">
        <Link to="/dashboard"><Button variant="ghost" className="mb-6"><ArrowLeft className="w-4 h-4 mr-2" />Retour</Button></Link>
        <h1 className="text-3xl font-bold mb-4">Centre de contestations</h1>
        <div className="bg-white p-8 rounded-lg border border-slate-200">
          <p className="text-slate-600">Les contestations apparaîtront ici.</p>
        </div>
      </div>
    </div>
  );
}
