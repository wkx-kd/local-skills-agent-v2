import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';

export function useAuth(requireAuth = true) {
  const { isAuthenticated, loading, fetchUser } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated && !useAuthStore.getState().user) {
      fetchUser();
    }
  }, [isAuthenticated, fetchUser]);

  useEffect(() => {
    if (requireAuth && !isAuthenticated && !loading) {
      navigate('/login');
    }
  }, [requireAuth, isAuthenticated, loading, navigate]);

  return { isAuthenticated, loading };
}
