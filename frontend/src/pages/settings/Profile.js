import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { ArrowLeft } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

export default function Profile() {
  const { user } = useAuth();
  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-4xl mx-auto">
        <Link to="/settings"><Button variant="ghost" className="mb-6"><ArrowLeft className="w-4 h-4 mr-2" />Retour</Button></Link>
        <h1 className="text-3xl font-bold mb-8">Mon profil</h1>
        <div className="bg-white p-8 rounded-lg border border-slate-200">
          <div className="space-y-4">
            <div><span className="font-medium">Nom:</span> {user?.first_name} {user?.last_name}</div>
            <div><span className="font-medium">Email:</span> {user?.email}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
