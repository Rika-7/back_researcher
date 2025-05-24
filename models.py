from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, DECIMAL
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Company(Base):
    __tablename__ = 'company'

    company_id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String, nullable=False)
    contract_plan = Column(String, nullable=False)

    users = relationship("CompanyUser", back_populates="company", cascade="all, delete")

class CompanyUser(Base):
    __tablename__ = 'company_user'

    company_user_id = Column(Integer, primary_key=True, autoincrement=True)
    company_user_name = Column(String, nullable=False)
    company_id = Column(Integer, ForeignKey('company.company_id'), nullable=False)
    department = Column(String, nullable=True)
    email_address = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)

    company = relationship("Company", back_populates="users")
    projects = relationship("ProjectInformation", back_populates="company_user", cascade="all, delete")

class ProjectInformation(Base):
    __tablename__ = "project_information"

    project_id = Column(Integer, primary_key=True, autoincrement=True)
    company_user_id = Column(Integer, ForeignKey('company_user.company_user_id'), nullable=False)
    project_title = Column(String(255), nullable=False)
    consultation_category = Column(String(255), nullable=False)
    project_content = Column(Text, nullable=False)
    research_field = Column(String(255), nullable=True)
    preferred_researcher_level = Column(String(255), nullable=True)
    application_deadline = Column(DateTime, nullable=False)
    project_status = Column(Integer, nullable=False, default=0)
    closed_date = Column(DateTime, nullable=True)
    industry_temp = Column(String(255), nullable=True)
    business_temp = Column(String(255), nullable=True)
    university_temp = Column(String(255), nullable=True)
    detailed_task = Column(Text, nullable=True)
    budget = Column(DECIMAL(12, 0), nullable=True)
    registration_date = Column(DateTime, nullable=False)

    company_user = relationship("CompanyUser", back_populates="projects")
    matchings = relationship("MatchingInformation", back_populates="project")

class ResearcherInformation(Base):
    __tablename__ = 'researcher_information'

    researcher_id = Column(Integer, primary_key=True, autoincrement=True)
    researcher_name = Column(String, nullable=False)
    researcher_name_kana = Column(String, nullable=True)
    researcher_name_alphabet = Column(String, nullable=True)
    researcher_affiliation_current = Column(String, nullable=True)
    # university_research_institution = Column(String, nullable=True)
    # affiliation = Column(String, nullable=True)
    researcher_department_current = Column(String, nullable=True)
    # position = Column(String, nullable=True)
    researcher_position_current = Column(String, nullable=True)
    researcher_affiliations_past = Column(String, nullable=True)
    # kaken_url = Column(String, nullable=True)
    research_field_pi = Column(String, nullable=True)
    keywords_pi = Column(String, nullable=True)
    researcher_email = Column(String, nullable=True, unique=True)
    researcher_password = Column(String, nullable=True)
    # email_address = Column(String, nullable=False, unique=True)
    # password = Column(String, nullable=False)

    matchings = relationship("MatchingInformation", back_populates="researcher")
    research_projects = relationship("ResearchProject", back_populates="researcher", cascade="all, delete")

class ResearchProject(Base):
    __tablename__ = 'research_project'

    research_project_id = Column(Integer, primary_key=True, autoincrement=True)
    researcher_id = Column(Integer, ForeignKey('researcher_information.researcher_id'), nullable=False)
    research_project_title = Column(String)
    research_project_details = Column(String)
    research_field = Column(String)
    research_achievement = Column(String)

    # リレーション
    researcher = relationship("ResearcherInformation", back_populates="research_projects")

class MatchingInformation(Base):
    __tablename__ = 'matching_information'

    matching_id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('project_information.project_id'), nullable=False)
    researcher_id = Column(Integer, ForeignKey('researcher_information.researcher_id'), nullable=False)
    matching_reason = Column(String, nullable=False)
    matching_status = Column(Integer, nullable=False, default=0)
    matched_date = Column(DateTime, nullable=False)

    project = relationship("ProjectInformation", back_populates="matchings")
    researcher = relationship("ResearcherInformation", back_populates="matchings")
    messages = relationship("MessageInformation", back_populates="matching", cascade="all, delete")

class MessageInformation(Base):
    __tablename__ = 'message_information'

    message_id = Column(Integer, primary_key=True, autoincrement=True)
    matching_id = Column(Integer, ForeignKey('matching_information.matching_id'), nullable=False)
    message_content = Column(String)
    sender_classification = Column(Integer)
    post_datetime = Column(DateTime)
    message_status = Column(Integer)

    # リレーション
    matching = relationship("MatchingInformation", back_populates="messages")