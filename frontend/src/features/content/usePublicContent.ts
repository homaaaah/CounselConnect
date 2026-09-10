/**
 * usePublicContent — published landing content + active emergency contacts.
 * (ERD content_items/emergency_contacts; DFD D8 public reads.)
 */
import { useEffect, useState } from "react";
import { request } from "../../services/apiClient";

export interface ContentItem {
  content_id: number;
  content_type: "CMS_BLOCK" | "FAQ" | "ANNOUNCEMENT";
  content_key: string | null;
  title: string | null;
  body: string;
  updated_at: string;
}

export interface EmergencyContact {
  contact_id: number;
  name: string;
  contact_number: string;
  description: string | null;
}

interface ListEnvelope<T> {
  items: T[];
}

export function usePublicContent() {
  const [cmsBlocks, setCmsBlocks] = useState<ContentItem[]>([]);
  const [faqs, setFaqs] = useState<ContentItem[]>([]);
  const [announcements, setAnnouncements] = useState<ContentItem[]>([]);
  const [contacts, setContacts] = useState<EmergencyContact[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [b, f, a, c] = await Promise.all([
          request<ListEnvelope<ContentItem>>("/content/cms-blocks"),
          request<ListEnvelope<ContentItem>>("/content/faqs"),
          request<ListEnvelope<ContentItem>>("/content/announcements"),
          request<ListEnvelope<EmergencyContact>>("/content/emergency-contacts"),
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
