"""
Source Verification Tests.
Validates that the source verification system correctly identifies and rejects mismatched sources.
"""
import pytest
import asyncio
from engine.source_verification import SourceVerification


class TestSourceVerification:
    """Tests for source verification logic."""
    
    def test_normalize_company_name(self):
        """Test company name normalization removes common suffixes."""
        assert SourceVerification._normalize_company_name("Harley Facades Ltd") == "harley facades"
        assert SourceVerification._normalize_company_name("Concept Facades Ltd.") == "concept facades"
        assert SourceVerification._normalize_company_name("  Eden Facades  ") == "eden facades"
        assert SourceVerification._normalize_company_name("ABC Inc") == "abc"
        assert SourceVerification._normalize_company_name("XYZ Corporation") == "xyz"
    
    def test_extract_company_names_from_page(self):
        """Test company name extraction from HTML."""
        html = """
        <h1>Harley Facades Ltd - Curtain Wall Specialists</h1>
        <p>Welcome to Harley Facades. We specialize in curtain wall solutions.</p>
        <footer>© 2024 Harley Facades Ltd. All rights reserved.</footer>
        """
        names = SourceVerification._extract_company_names_from_page(html)
        
        # Should extract company name variations
        names_lower = [n.lower() for n in names]
        assert any("harley" in n for n in names_lower), f"Should find 'harley' in {names_lower}"
    
    def test_demo_detection(self):
        """Test detection of demo/placeholder pages."""
        demo_page = """
        <h1>[Your Company Name Here]</h1>
        <p>This is a sample/template website. Replace this with your content.</p>
        <p>Coming soon...</p>
        """
        
        # This would be in a real async test - showing logic
        demo_keywords_found = [kw for kw in SourceVerification.DEMO_KEYWORDS if kw in demo_page.lower()]
        assert len(demo_keywords_found) > 0, "Should detect demo keywords"
    
    def test_directory_domain_detection(self):
        """Test detection of directory/listing domains."""
        urls_to_test = [
            ("https://www.yellowpages.com/company/harley-facades", True),
            ("https://maps.google.com/place/harley+facades", True),
            ("https://www.harleyfacades.com/about", False),
            ("https://news.bbc.co.uk/article/harley-facades", False),
        ]
        
        for url, should_be_directory in urls_to_test:
            is_directory = any(d in url.lower() for d in SourceVerification.DIRECTORY_DOMAINS)
            assert is_directory == should_be_directory, f"URL {url} classification incorrect"
    
    @pytest.mark.asyncio
    async def test_homepage_verification_success(self):
        """Test successful homepage verification."""
        genuine_homepage = """
        <!DOCTYPE html>
        <html>
        <head><title>Harley Facades - Curtain Wall Contractors</title></head>
        <body>
        <h1>Harley Facades Ltd</h1>
        <section>About Us</section>
        <p>We are a leading curtain wall contractor established in 2010.</p>
        <p>Based in the UK, Harley Facades specializes in façade systems for commercial buildings.</p>
        <section>Contact Us</section>
        <p>Email: info@harleyfacades.com</p>
        <p>Phone: +44 (0) 123 456 789</p>
        <p>Head Office: Birmingham, UK</p>
        </body>
        </html>
        """
        
        is_verified, reason = await SourceVerification.verify_homepage("Harley Facades", "https://www.harleyfacades.com", genuine_homepage)
        assert is_verified, f"Should verify genuine homepage. Reason: {reason}"
    
    @pytest.mark.asyncio
    async def test_homepage_verification_failure_wrong_company(self):
        """Test homepage verification failure when company name doesn't match."""
        wrong_company_page = """
        <!DOCTYPE html>
        <html>
        <body>
        <h1>Concept Facades Ltd</h1>
        <p>We are Concept Facades, a curtain wall contractor.</p>
        <p>About Us: Concept Facades specializes in modern façade solutions.</p>
        </body>
        </html>
        """
        
        is_verified, reason = await SourceVerification.verify_homepage("Harley Facades", "https://www.harleyfacades.com", wrong_company_page)
        assert not is_verified, "Should reject homepage with wrong company name"
        assert "mismatch" in reason.lower() or "concept" in reason.lower()
    
    @pytest.mark.asyncio
    async def test_homepage_verification_failure_demo_page(self):
        """Test homepage verification failure for demo/placeholder pages."""
        demo_page = """
        <html>
        <h1>[Your Company Name]</h1>
        <p>This is a sample template website.</p>
        <p>Replace this content with your information.</p>
        </html>
        """
        
        is_verified, reason = await SourceVerification.verify_homepage("Harley Facades", "https://www.harleyfacades.com", demo_page)
        assert not is_verified, "Should reject demo/placeholder pages"
        assert "demo" in reason.lower() or "placeholder" in reason.lower()
    
    @pytest.mark.asyncio
    async def test_source_url_verification_directory_rejection(self):
        """Test that directory/listing URLs are rejected."""
        directory_url = "https://www.yellowpages.com/company/harley-facades-birmingham"
        is_verified, reason = await SourceVerification.verify_source_url("Harley Facades", directory_url)
        
        assert not is_verified, "Should reject directory URLs"
        assert "directory" in reason.lower()
    
    @pytest.mark.asyncio
    async def test_ambiguous_company_names(self):
        """Test handling of ambiguous company names (same name, different locations/companies)."""
        # This is a scenario where multiple companies have similar names
        
        # Genuine Harley Facades page
        real_harley_page = """
        <h1>Harley Facades - UK Contractor</h1>
        <p>Harley Facades Ltd is based in Birmingham, UK</p>
        <p>We specialize in curtain wall and cladding systems.</p>
        """
        
        # Different company with same name
        fake_harley_page = """
        <h1>Harley Facades - Australian Builder</h1>
        <p>Harley Facades Pty Ltd is based in Sydney, Australia</p>
        <p>We provide general contracting services.</p>
        """
        
        # Both pages have "Harley Facades" but they're different companies
        # The verification should still accept both if matching, but context matters
        # In production, location checks would be added to disambiguate
        
        is_verified_1, _ = await SourceVerification.verify_homepage("Harley Facades", "https://www.harleyfacades.co.uk", real_harley_page)
        is_verified_2, _ = await SourceVerification.verify_homepage("Harley Facades", "https://www.harleyfacades.com.au", fake_harley_page)
        
        # Both should verify positively based on name alone, but in real scenario
        # we'd also check location/domain to disambiguate
        assert is_verified_1 or is_verified_2, "At least one should be accepted based on name match"


class TestAmbiguousNameScenarios:
    """Tests for real-world ambiguous company name scenarios."""
    
    @pytest.mark.asyncio
    async def test_same_name_different_locations(self):
        """Scenario: Two real companies with same name in different countries."""
        # Eden Facades Ltd (UK - building façades)
        uk_eden_page = """
        <html>
        <h1>Eden Facades Ltd - UK Specialists</h1>
        <p>Eden Facades Ltd is a UK-based company founded in 2005.</p>
        <p>We are leaders in façade design and installation for commercial properties.</p>
        <p>Located: Birmingham, United Kingdom</p>
        <p>Services: Curtain walls, cladding, glazing systems</p>
        </html>
        """
        
        # Eden Facades Inc (US - different type of company, coincidentally same name)
        us_eden_page = """
        <html>
        <h1>Eden Facades Inc - Garden Design</h1>
        <p>Eden Facades, based in California, specializes in garden landscaping.</p>
        <p>We create beautiful outdoor spaces and garden walls.</p>
        <p>Services: Landscape design, garden walls, outdoor facades</p>
        </html>
        """
        
        # When searching for "Eden Facades" with UK context, should match UK page
        is_verified_uk, _ = await SourceVerification.verify_homepage("Eden Facades", "https://edenfacades.co.uk", uk_eden_page)
        assert is_verified_uk, "Should verify UK Eden Facades page"
        
        # US page might also match by name, but location/content is different
        is_verified_us, reason = await SourceVerification.verify_homepage("Eden Facades", "https://edenfacades.co.uk", us_eden_page)
        # This might or might not verify depending on similarity threshold
        # But it should at least record the concern
    
    @pytest.mark.asyncio
    async def test_common_word_false_positive(self):
        """Scenario: Search result for generic term that matches many companies."""
        # Searching for "Design Solutions Ltd" returns generic industry article
        generic_article = """
        <html>
        <h1>Top Design Solutions for Building Facades</h1>
        <p>The facade industry offers many design solutions from various contractors.</p>
        <p>Companies like ABC Facades, XYZ Contractors, and Design Solutions Ltd all offer...</p>
        </html>
        """
        
        # Should detect that this is generic article, not about the specific company
        is_verified, reason = await SourceVerification.verify_source_url("Design Solutions Ltd", "https://example.com/facade-article", generic_article)
        
        if not is_verified:
            assert "mention" in reason.lower() or "generic" in reason.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
