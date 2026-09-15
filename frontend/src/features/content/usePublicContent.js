/**
 * usePublicContent — published landing content + active emergency contacts.
 * (ERD content_items/emergency_contacts; DFD D8 public reads.)
 */
import { useEffect, useState } from "react";
import { request } from "../../services/apiClient";

export function usePublicContent() {
  const [cmsBlocks, setCmsBlocks] = useState([]);
  const [faqs, setFaqs] = useState([]);
  const [announcements, setAnnouncements] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [b, f, a, c] = await Promise.all([
          request("/content/cms-blocks"),
          request("/content/faqs"),
          request("/content/announcements"),
          request("/content/emergency-contacts"),
        ]);
        if (!cancelled) {
          setCmsBlocks(b.items);
          setFaqs(f.items);
          setAnnouncements(a.items);
          setContacts(c.items);
        }
      } catch {
        /* landing shows empty sections when the API is unreachable */
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return { cmsBlocks, faqs, announcements, contacts, loading };
}
