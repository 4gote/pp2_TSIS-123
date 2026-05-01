import psycopg2
from psycopg2 import sql, extras
import csv
import json
from datetime import datetime

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'phonebook',
    'user': 'postgres',
    'password': '12345'
}

class PhoneBook:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.conn.autocommit = False
            self.cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            self.create_tables()
            self.create_procedures()
        except psycopg2.Error as e:
            print(f"Database connection failed: {e}")
            raise

    def create_tables(self):
        queries = [
            """
            CREATE TABLE IF NOT EXISTS groups (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS contacts (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                email VARCHAR(100),
                birthday DATE,
                group_id INTEGER REFERENCES groups(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS phones (
                id SERIAL PRIMARY KEY,
                contact_id INTEGER REFERENCES contacts(id) ON DELETE CASCADE,
                phone VARCHAR(20) NOT NULL,
                type VARCHAR(10) CHECK (type IN ('home', 'work', 'mobile'))
            )
            """
        ]
        
        for query in queries:
            self.cursor.execute(query)
        self.conn.commit()
        
        default_groups = ['Family', 'Work', 'Friend', 'Other']
        for group in default_groups:
            self.cursor.execute(
                "INSERT INTO groups (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                (group,)
            )
        self.conn.commit()

    def create_procedures(self):
        add_phone_proc = """
        CREATE OR REPLACE PROCEDURE add_phone(
            p_contact_name VARCHAR,
            p_phone VARCHAR,
            p_type VARCHAR
        )
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_contact_id INTEGER;
        BEGIN
            SELECT id INTO v_contact_id FROM contacts WHERE name = p_contact_name;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Contact % not found', p_contact_name;
            END IF;
            INSERT INTO phones (contact_id, phone, type) 
            VALUES (v_contact_id, p_phone, p_type);
        END;
        $$;
        """
        
        move_to_group_proc = """
        CREATE OR REPLACE PROCEDURE move_to_group(
            p_contact_name VARCHAR,
            p_group_name VARCHAR
        )
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_group_id INTEGER;
            v_contact_id INTEGER;
        BEGIN
            SELECT id INTO v_group_id FROM groups WHERE name = p_group_name;
            IF NOT FOUND THEN
                INSERT INTO groups (name) VALUES (p_group_name) RETURNING id INTO v_group_id;
            END IF;
            SELECT id INTO v_contact_id FROM contacts WHERE name = p_contact_name;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Contact % not found', p_contact_name;
            END IF;
            UPDATE contacts SET group_id = v_group_id WHERE id = v_contact_id;
        END;
        $$;
        """
        
        search_func = """
        CREATE OR REPLACE FUNCTION search_contacts(p_query TEXT)
        RETURNS TABLE(
            contact_name VARCHAR,
            email VARCHAR,
            birthday DATE,
            group_name VARCHAR,
            phones JSONB
        )
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RETURN QUERY
            SELECT DISTINCT
                c.name AS contact_name,
                c.email,
                c.birthday,
                g.name AS group_name,
                COALESCE(
                    (SELECT jsonb_agg(jsonb_build_object('phone', p.phone, 'type', p.type))
                     FROM phones p WHERE p.contact_id = c.id),
                    '[]'::jsonb
                ) AS phones
            FROM contacts c
            LEFT JOIN groups g ON c.group_id = g.id
            WHERE 
                c.name ILIKE '%' || p_query || '%'
                OR c.email ILIKE '%' || p_query || '%'
                OR EXISTS (
                    SELECT 1 FROM phones p 
                    WHERE p.contact_id = c.id 
                    AND p.phone ILIKE '%' || p_query || '%'
                );
        END;
        $$;
        """
        
        for proc in [add_phone_proc, move_to_group_proc, search_func]:
            try:
                self.cursor.execute(proc)
            except psycopg2.Error:
                pass
        self.conn.commit()

    def add_contact(self, name, email=None, birthday=None, group_name=None):
        try:
            group_id = None
            if group_name:
                self.cursor.execute("SELECT id FROM groups WHERE name = %s", (group_name,))
                result = self.cursor.fetchone()
                if result:
                    group_id = result['id']
                else:
                    print(f"Group '{group_name}' not found. Using default.")
            
            self.cursor.execute(
                """INSERT INTO contacts (name, email, birthday, group_id) 
                   VALUES (%s, %s, %s, %s) RETURNING id""",
                (name, email, birthday, group_id)
            )
            contact_id = self.cursor.fetchone()['id']
            self.conn.commit()
            print(f"Contact '{name}' added successfully with ID: {contact_id}")
            return contact_id
        except psycopg2.IntegrityError:
            self.conn.rollback()
            print(f"Error: Contact '{name}' already exists!")
            return None
        except Exception as e:
            self.conn.rollback()
            print(f"Error adding contact: {e}")
            return None

    def add_phone(self, contact_name, phone, phone_type='mobile'):
        try:
            self.cursor.callproc('add_phone', (contact_name, phone, phone_type))
            self.conn.commit()
            print(f"Phone {phone} ({phone_type}) added to {contact_name}")
            return True
        except psycopg2.Error as e:
            self.conn.rollback()
            print(f"Error adding phone: {e}")
            return False

    def move_to_group(self, contact_name, group_name):
        try:
            self.cursor.callproc('move_to_group', (contact_name, group_name))
            self.conn.commit()
            print(f"Contact '{contact_name}' moved to group '{group_name}'")
            return True
        except psycopg2.Error as e:
            self.conn.rollback()
            print(f"Error moving contact: {e}")
            return False

    def search_contacts(self, query):
        self.cursor.execute("SELECT * FROM search_contacts(%s)", (query,))
        results = self.cursor.fetchall()
        return results

    def filter_by_group(self, group_name, page=1, page_size=10):
        offset = (page - 1) * page_size
        self.cursor.execute(
            """SELECT c.name, c.email, c.birthday, g.name as group_name,
                      array_agg(p.phone || ' (' || p.type || ')') as phones
               FROM contacts c
               LEFT JOIN groups g ON c.group_id = g.id
               LEFT JOIN phones p ON c.id = p.contact_id
               WHERE g.name = %s
               GROUP BY c.id, g.name
               ORDER BY c.name
               LIMIT %s OFFSET %s""",
            (group_name, page_size, offset)
        )
        return self.cursor.fetchall()

    def sort_contacts(self, sort_by='name', order='ASC'):
        valid_fields = {'name', 'birthday', 'created_at'}
        if sort_by not in valid_fields:
            print(f"Invalid sort field. Use: {valid_fields}")
            return []
        
        query = f"""
            SELECT c.name, c.email, c.birthday, c.created_at, g.name as group_name
            FROM contacts c
            LEFT JOIN groups g ON c.group_id = g.id
            ORDER BY {sort_by} {order}
        """
        self.cursor.execute(query)
        return self.cursor.fetchall()

    def export_to_json(self, filename=None):
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"contacts_export_{timestamp}.json"
        
        self.cursor.execute("""
            SELECT c.*, g.name as group_name,
                   json_agg(json_build_object('phone', p.phone, 'type', p.type)) as phones
            FROM contacts c
            LEFT JOIN groups g ON c.group_id = g.id
            LEFT JOIN phones p ON c.id = p.contact_id
            GROUP BY c.id, g.name
        """)
        contacts = self.cursor.fetchall()
        
        export_data = []
        for contact in contacts:
            contact_dict = dict(contact)
            if contact_dict.get('birthday'):
                contact_dict['birthday'] = str(contact_dict['birthday'])
            if contact_dict.get('created_at'):
                contact_dict['created_at'] = str(contact_dict['created_at'])
            if contact_dict.get('phones') and contact_dict['phones'][0] is None:
                contact_dict['phones'] = []
            export_data.append(contact_dict)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(export_data)} contacts to {filename}")
        return filename

    def import_from_json(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                contacts_data = json.load(f)
            
            imported = 0
            skipped = 0
            
            for contact_data in contacts_data:
                self.cursor.execute("SELECT id FROM contacts WHERE name = %s", 
                                  (contact_data['name'],))
                exists = self.cursor.fetchone()
                
                if exists:
                    print(f"Contact '{contact_data['name']}' already exists. Skip? (y/n)")
                    choice = input().lower()
                    if choice == 'y':
                        skipped += 1
                        continue
                
                contact_id = self.add_contact(
                    contact_data['name'],
                    contact_data.get('email'),
                    contact_data.get('birthday'),
                    contact_data.get('group_name')
                )
                
                if contact_id and contact_data.get('phones'):
                    for phone_data in contact_data['phones']:
                        self.add_phone(
                            contact_data['name'],
                            phone_data['phone'],
                            phone_data.get('type', 'mobile')
                        )
                    imported += 1
            
            print(f"Import complete: {imported} added, {skipped} skipped")
            return True
            
        except Exception as e:
            print(f"Error importing from JSON: {e}")
            return False

    def import_from_csv(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
            
            imported = 0
            for row in reader:
                contact_id = self.add_contact(
                    row['name'],
                    row.get('email'),
                    row.get('birthday'),
                    row.get('group')
                )
                if contact_id and row.get('phone'):
                    self.add_phone(
                        row['name'],
                        row['phone'],
                        row.get('phone_type', 'mobile')
                    )
                    imported += 1
            
            print(f"Imported {imported} contacts from {filename}")
            return True
            
        except Exception as e:
            print(f"Error importing from CSV: {e}")
            return False

    def paginated_navigation(self, query_func, *args, page_size=5):
        page = 1
        while True:
            try:
                results = query_func(*args, page=page, page_size=page_size)
            except TypeError:
                results = query_func(*args)
                if not results:
                    break
                start = (page - 1) * page_size
                end = start + page_size
                results = results[start:end]
            
            if not results:
                print("No more results.")
                break
            
            print(f"\n--- Page {page} ---")
            for i, contact in enumerate(results, 1):
                print(f"{i}. {contact['name']} - {contact.get('email', 'No email')}")
                if 'phones' in contact and contact['phones']:
                    phones_str = ', '.join(contact['phones']) if isinstance(contact['phones'], list) else str(contact['phones'])
                    print(f"   Phones: {phones_str}")
            
            print("\nCommands: [n]ext, [p]revious, [q]uit")
            cmd = input("> ").lower()
            
            if cmd == 'n':
                page += 1
            elif cmd == 'p' and page > 1:
                page -= 1
            elif cmd == 'q':
                break

    def display_contacts(self, contacts=None):
        if contacts is None:
            self.cursor.execute("SELECT name, email, group_id FROM contacts ORDER BY name")
            contacts = self.cursor.fetchall()
        
        if not contacts:
            print("No contacts found")
            return
        
        print("\n" + "-" * 70)
        print(f"{'Name':<25} {'Email':<30} {'Group'}")
        print("-" * 70)
        for c in contacts:
            group_name = "None"
            if c.get('group_id'):
                self.cursor.execute("SELECT name FROM groups WHERE id = %s", (c['group_id'],))
                grp = self.cursor.fetchone()
                if grp:
                    group_name = grp['name']
            print(f"{c['name']:<25} {(c.get('email') or 'N/A'):<30} {group_name}")
        print("-" * 70)

    def close(self):
        if hasattr(self, 'cursor') and self.cursor:
            self.cursor.close()
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

def main():
    pb = PhoneBook()
    
    while True:
        print("\n" + "=" * 60)
        print("PHONEBOOK APPLICATION - PostgreSQL Version")
        print("=" * 60)
        print("1. Add Contact")
        print("2. Add Phone Number")
        print("3. Move Contact to Group")
        print("4. Search Contacts")
        print("5. Filter by Group")
        print("6. Sort Contacts")
        print("7. Export to JSON")
        print("8. Import from JSON")
        print("9. Import from CSV")
        print("10. Paginated Navigation")
        print("11. List All Contacts")
        print("0. Exit")
        print("-" * 60)
        
        choice = input("Enter choice: ")
        
        if choice == '1':
            name = input("Name: ")
            email = input("Email (optional): ") or None
            birthday = input("Birthday (YYYY-MM-DD, optional): ") or None
            group = input("Group (Family/Work/Friend/Other, optional): ") or None
            pb.add_contact(name, email, birthday, group)
        
        elif choice == '2':
            name = input("Contact name: ")
            phone = input("Phone number: ")
            ptype = input("Type (home/work/mobile): ") or 'mobile'
            pb.add_phone(name, phone, ptype)
        
        elif choice == '3':
            name = input("Contact name: ")
            group = input("New group name: ")
            pb.move_to_group(name, group)
        
        elif choice == '4':
            query = input("Search query: ")
            results = pb.search_contacts(query)
            for r in results:
                print(f"\n{r['contact_name']} ({r.get('group_name', 'No group')})")
                print(f"  Email: {r.get('email', 'N/A')}")
                print(f"  Birthday: {r.get('birthday', 'N/A')}")
                print(f"  Phones: {r['phones']}")
        
        elif choice == '5':
            group = input("Group name: ")
            results = pb.filter_by_group(group)
            for r in results:
                phones_str = ', '.join(r['phones']) if r['phones'] else 'No phones'
                print(f"{r['name']} - {r.get('email', 'N/A')} - Phones: {phones_str}")
        
        elif choice == '6':
            sort_by = input("Sort by (name/birthday/created_at): ")
            order = input("Order (ASC/DESC): ").upper()
            pb.sort_contacts(sort_by, order)
            pb.display_contacts()
        
        elif choice == '7':
            pb.export_to_json()
        
        elif choice == '8':
            filename = input("JSON filename: ")
            pb.import_from_json(filename)
        
        elif choice == '9':
            filename = input("CSV filename: ")
            pb.import_from_csv(filename)
        
        elif choice == '10':
            group = input("Group name: ")
            pb.paginated_navigation(pb.filter_by_group, group)
        
        elif choice == '11':
            pb.display_contacts()
        
        elif choice == '0':
            pb.close()
            print("Goodbye!")
            break

if __name__ == "__main__":
    main()